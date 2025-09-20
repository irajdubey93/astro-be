# app/services/chat_agent.py
import json
from sqlalchemy.orm import Session
from app.models import ChatSession, ChatMessage, Profile
from app.redis_client import get_redis
from app.utils.evaluator import evaluate_query
from google import genai
from app.config import GEMINI_API_KEY

# Gemini client
client = genai.Client(api_key=GEMINI_API_KEY)

# System prompt template
AGENT_PROMPT = """
You are an AI Vedic astrologer.

Always answer like an experienced Indian astrologer, 
using planetary positions, dashas, antardashas, and profile details.

Rules:
- Stay strictly in astrology domain.
- If asked about health/finance, mention astrological indicators but advise professional consultation.
- Be empathetic, guiding, and culturally sensitive.
- Use Vedic astrology terminology (e.g., Lagna, Mahadasha, Antardasha, Graha).
"""

async def generate_response(db: Session, session: ChatSession, profile: Profile, query: str):
    # ✅ Guardrails
    safe = await evaluate_query(query)
    if not safe:
        return "🚫 Sorry, I cannot answer this type of query."

    # ✅ Redis connection
    redis = await get_redis()

    # ✅ Fetch chat history from Redis
    messages_key = f"chat:messages:{session.id}"
    chat_history = await redis.lrange(messages_key, 0, -1)
    chat_history = [json.loads(msg) for msg in chat_history]

    # ✅ Format profile data
    profile_data = {
        "name": profile.full_name,
        "dob": str(profile.date_of_birth),
        "time": str(profile.birth_time),
        "place": profile.birth_place_name,
        "lat": profile.birth_lat,
        "lon": profile.birth_lon,
        "tz": profile.birth_tz,
    }

    # ✅ Build prompt for Gemini (user role only)
    prompt_text = (
        f"{AGENT_PROMPT}\n\n"
        f"Profile Data: {json.dumps(profile_data)}\n"
        f"Planetary Positions: {json.dumps(profile.planetary_positions)}\n"
        f"Dasha Details: {json.dumps(profile.dasha_details)}\n"
        f"Chat History: {json.dumps(chat_history)}\n\n"
        f"User Query: {query}\n"
    )

    # ✅ Call Gemini LLM
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[{"role": "user", "parts": [{"text": prompt_text}]}],
    )

    answer = response.candidates[0].content.parts[0].text.strip()

    # ✅ Save conversation in DB
    user_msg = ChatMessage(session_id=session.id, sender="user", message=query)
    agent_msg = ChatMessage(session_id=session.id, sender="agent", message=answer)
    db.add_all([user_msg, agent_msg])
    db.commit()

    # ✅ Save in Redis (append new messages)
    await redis.rpush(messages_key, json.dumps({"role": "user", "content": query}))
    await redis.rpush(messages_key, json.dumps({"role": "agent", "content": answer}))

    # ✅ Expire after 7 days
    await redis.expire(messages_key, 60 * 60 * 24 * 7)

    return answer