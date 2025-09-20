# app/services/chat_agent.py
import json
from datetime import datetime
from dateutil import parser as date_parser
from sqlalchemy.orm import Session
from app.models import ChatSession, ChatMessage, Profile
from app.redis_client import get_redis
from app.utils.evaluator import evaluate_query, evaluate_output, extract_reference_date
from google import genai
from app.config import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)


# ------------------------
# System Prompts
# ------------------------
SYSTEM_PROMPT = """
You are a highly knowledgeable and empathetic Indian Vedic astrologer.

Rules:
- STRICTLY use planetary positions and Dasha/Antardasha from profile data.
- If the user specifies a timeframe (e.g. "next 2 weeks" or "January 2026"), use that as the reference date.
- If no date is specified, default to TODAY: {reference_date}.
- Do NOT invent dates. Use saved dasha periods to explain timing.
- Always explain logic with Grahas (planets), Rashis (signs), Bhavas (houses), and Dashas.
- Use empathetic, spiritual, and guiding tone.
- End with a concise summary (≤3 lines).
"""

FALLBACK_PROMPT = """
You are a strict Vedic astrologer. 
Answer ONLY with Graha, Bhava, and Dasha/Antardasha logic from provided data.
Base analysis on reference date: {reference_date}.
Do not provide vague, generic advice.
"""


# ------------------------
# Main Response Generator
# ------------------------
async def generate_response(db: Session, session: ChatSession, profile: Profile, query: str):
    redis_conn = await get_redis()

    # ✅ Step 1: Input Guardrail
    safe = await evaluate_query(query)
    if not safe:
        return "🚫 Sorry, I cannot answer this type of query."

    # ✅ Step 2: Chat history
    messages_key = f"chat:messages:{session.id}"
    chat_history = await redis_conn.lrange(messages_key, 0, -1)
    chat_history = [json.loads(msg) for msg in chat_history]
    chat_history_text = "\n".join([f"{m['role']}: {m['content']}" for m in chat_history])

    # ✅ Step 3: Determine reference date
    extracted_date = await extract_reference_date(query)
    if extracted_date:
        reference_date = extracted_date
    else:
        reference_date = datetime.utcnow().strftime("%Y-%m-%d")

    # ✅ Step 4: Build astrology context
    profile_context = f"""
    Name: {profile.full_name}
    DOB: {profile.date_of_birth}, Time: {profile.birth_time}
    Place: {profile.birth_place_name} (Lat: {profile.birth_lat}, Lon: {profile.birth_lon}, TZ: {profile.birth_tz})
    """

    planetary_context = json.dumps(profile.planetary_positions, indent=2)
    dasha_context = json.dumps(profile.dasha_details, indent=2)

    def build_prompt(base_prompt: str):
        return f"""
{base_prompt.format(reference_date=reference_date)}

### User Profile
{profile_context}

### Planetary Positions
{planetary_context}

### Dasha Details
{dasha_context}

### Chat History
{chat_history_text}

### User Query
{query}
"""

    # ✅ Step 5: Primary response attempt
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[{"role": "user", "parts": [{"text": build_prompt(SYSTEM_PROMPT)}]}],
    )
    answer = response.candidates[0].content.parts[0].text.strip()

    # ✅ Step 6: Output Guardrail
    valid = await evaluate_output(answer)

    # Retry with fallback if unsafe/invalid
    if not valid:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[{"role": "user", "parts": [{"text": build_prompt(FALLBACK_PROMPT)}]}],
        )
        answer = response.candidates[0].content.parts[0].text.strip()
        valid = await evaluate_output(answer)

    # Final fallback
    if not valid:
        answer = (
            f"🙏 Based on your planetary positions and Dasha periods as of {reference_date}, "
            "the influences are mixed. Focus on patience, discipline, and spiritual balance. "
            "Would you like me to analyze your Antardasha in detail for this period?"
        )

    # ✅ Step 7: Save conversation (DB + Redis)
    user_msg = ChatMessage(session_id=session.id, sender="user", message=query)
    agent_msg = ChatMessage(session_id=session.id, sender="agent", message=answer)
    db.add_all([user_msg, agent_msg])
    db.commit()

    await redis_conn.rpush(messages_key, json.dumps({"role": "user", "content": query}))
    await redis_conn.rpush(messages_key, json.dumps({"role": "agent", "content": answer}))
    await redis_conn.expire(messages_key, 60 * 60 * 24 * 7)  # 7 days expiry

    return answer