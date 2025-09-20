# app/routes/chat.py
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from app.database import get_db
from app.models import ChatSession, ChatMessage, Profile, User
from app.services.chat_agent import generate_response
from app.utils.jwt_handler import verify_access_token
from google import genai
from app.config import GEMINI_API_KEY

router = APIRouter()

# Gemini Client
client = genai.Client(api_key=GEMINI_API_KEY)


# ---------------------------
# Auth helper
# ---------------------------
def get_current_user(authorization: str = Header(...), db: Session = Depends(get_db)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.split(" ")[1]
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


# ---------------------------
# Start Chat Session
# ---------------------------
@router.post("/chat/start/{profile_id}")
def start_chat(
    profile_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = (
        db.query(Profile)
        .filter(Profile.id == profile_id, Profile.user_id == current_user.id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    session = ChatSession(
        user_id=current_user.id, profile_id=profile.id, created_at=datetime.utcnow()
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return {"session_id": session.id, "message": "Chat session started ✅"}


# ---------------------------
# Ask Query
# ---------------------------
@router.post("/chat/query/{session_id}")
async def ask_query(
    session_id: str,
    query: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    profile = db.query(Profile).filter(Profile.id == session.profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    answer = await generate_response(db, session, profile, query)

    return {"query": query, "answer": answer}


# ---------------------------
# Follow-up Question (Cross-questioning)
# ---------------------------
@router.post("/chat/followup/{session_id}/{message_id}")
async def followup_query(
    session_id: str,
    message_id: str,
    query: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Ask a follow-up question tied to a specific past message.
    Example: "In message #5 you said I'd get a job after Oct 2024, 
    can you explain why not earlier?"
    """
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    # Fetch the referenced message
    reference_msg = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id, ChatMessage.id == message_id)
        .first()
    )
    if not reference_msg:
        raise HTTPException(status_code=404, detail="Referenced message not found")

    profile = db.query(Profile).filter(Profile.id == session.profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Build enriched query
    enriched_query = f"""
    The user is asking a follow-up about this previous astrologer response:

    ----
    {reference_msg.message}
    ----

    Follow-up question: {query}
    """

    answer = await generate_response(db, session, profile, enriched_query)

    return {
        "followup_to": message_id,
        "query": query,
        "answer": answer,
    }


# ---------------------------
# Get Full Conversation (Paginated)
# ---------------------------
@router.get("/chat/conversation/{session_id}")
async def get_full_conversation(
    session_id: str,
    limit: int = Query(20, ge=1, le=100, description="Number of messages to fetch"),
    offset: int = Query(0, ge=0, description="Number of messages to skip"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    query = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.asc())
    )

    total = query.count()
    messages = query.offset(offset).limit(limit).all()

    conversation = [
        {
            "id": str(msg.id),
            "sender": msg.sender,
            "message": msg.message,
            "timestamp": msg.created_at.isoformat(),
        }
        for msg in messages
    ]

    return {
        "session_id": session.id,
        "total_messages": total,
        "limit": limit,
        "offset": offset,
        "conversation": conversation,
    }


# ---------------------------
# Search in Conversation
# ---------------------------
@router.get("/chat/search/{session_id}")
async def search_conversation(
    session_id: str,
    q: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id, ChatMessage.message.ilike(f"%{q}%"))
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    return [
        {
            "id": str(msg.id),
            "sender": msg.sender,
            "message": msg.message,
            "timestamp": msg.created_at.isoformat(),
        }
        for msg in messages
    ]


# ---------------------------
# Summarize Conversation
# ---------------------------
@router.get("/chat/summary/{session_id}")
async def summarize_conversation(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    if not messages:
        return {"session_id": session.id, "summary": "No messages yet in this session."}

    conversation_text = "\n".join([f"{m.sender}: {m.message}" for m in messages])

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            {
                "role": "user",
                "parts": [
                    {
                        "text": f"Summarize this astrology chat conversation in a concise, empathetic way:\n\n{conversation_text}"
                    }
                ],
            }
        ],
    )

    summary = response.candidates[0].content.parts[0].text.strip()
    return {"session_id": session.id, "summary": summary}