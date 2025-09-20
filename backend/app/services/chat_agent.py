import json
import openai
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import ChatMessage, ChatSession, Profile
from app.redis_client import get_redis
from app.config import DIVINE_API_KEY, DIVINE_AUTH_TOKEN

# 🚨 Guardrails evaluator
def evaluate_query(query: str) -> bool:
    blocked = ["suicide", "kill myself", "medical diagnosis", "illegal", "lottery"]
    return not any(word in query.lower() for word in blocked)

# 🧠 System Prompt Template
AGENT_PROMPT = """
You are an AI Astrologer. 
Answer based on:
- User profile: {profile_data}
- Planetary positions: {planetary_positions}
- Dasha details: {dasha_details}
- Chat history: {chat_history}

Rules:
- Stick strictly to astrology context.
- Explain using Vedic astrology logic (dashas, planetary positions, houses).
- For health/finance → give astrological indicators but recommend professional help.
- Use an empathetic, guiding, and positive tone.
"""

async def generate_response(db: Session, session: ChatSession, profile: Profile, query: str):
    redis_conn = await get_redis()

    # 🚨 Guardrails
    if not evaluate_query(query):
        return "🚫 Sorry, I cannot answer this type of query."

    # ♻️ Cache astrology data in Redis
    astrology_key = f"profile:{profile.id}:astrology"
    astrology_data = await redis_conn.get(astrology_key)
    if astrology_data:
        astrology_data = json.loads(astrology_data)
    else:
        astrology_data = {
            "planetary_positions": profile.planetary_positions,
            "dasha_details": profile.dasha_details,
        }
        await redis_conn.setex(astrology_key, 3600, json.dumps(astrology_data))  # 1h cache

    # 💬 Fetch chat history from Redis
    messages_key = f"chat:messages:{session.id}"
    chat_history = await redis_conn.lrange(messages_key, 0, -1)
    chat_history = [json.loads(msg) for msg in chat_history]

    # 📝 System Prompt
    prompt = AGENT_PROMPT.format(
        profile_data=json.dumps({
            "name": profile.full_name,
            "dob": str(profile.date_of_birth),
            "time": str(profile.birth_time),
            "place": profile.birth_place_name,
            "lat": profile.birth_lat,
            "lon": profile.birth_lon,
            "tz": profile.birth_tz,
        }),
        planetary_positions=json.dumps(astrology_data.get("planetary_positions")),
        dasha_details=json.dumps(astrology_data.get("dasha_details")),
        chat_history=json.dumps(chat_history),
    )

    # 🤖 Call OpenAI
    response = await openai.ChatCompletion.acreate(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": query},
        ],
        max_tokens=500,
    )
    answer = response.choices[0].message["content"]

    # 💾 Save to DB
    user_msg = ChatMessage(session_id=session.id, sender="user", message=query)
    agent_msg = ChatMessage(session_id=session.id, sender="agent", message=answer)
    db.add_all([user_msg, agent_msg])
    db.commit()

    # 💾 Save to Redis
    await redis_conn.rpush(messages_key, json.dumps({"role": "user", "content": query}))
    await redis_conn.rpush(messages_key, json.dumps({"role": "agent", "content": answer}))
    await redis_conn.expire(messages_key, 60 * 60 * 24 * 7)  # 7 days

    return answer