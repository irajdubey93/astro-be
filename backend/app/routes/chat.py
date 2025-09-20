# app/routes/chat.py
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.database import get_db
from app.models import ChatSession, ChatMessage, Profile, User
from app.services.chat_agent import generate_response
from app.utils.jwt_handler import verify_access_token

router = APIRouter()


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
def start_chat(profile_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    profile = db.query(Profile).filter(Profile.id == profile_id, Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Create a new session
    session = ChatSession(user_id=current_user.id, profile_id=profile.id, created_at=datetime.utcnow())
    db.add(session)
    db.commit()
    db.refresh(session)

    return {"session_id": session.id, "message": "Chat session started ✅"}


# ---------------------------
# Ask Query
# ---------------------------
@router.post("/chat/query/{session_id}")
async def ask_query(session_id: str, query: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    profile = db.query(Profile).filter(Profile.id == session.profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Generate AI astrologer response
    answer = await generate_response(db, session, profile, query)

    return {"query": query, "answer": answer}


# ---------------------------
# Get Chat History
# ---------------------------
@router.get("/chat/history/{session_id}")
def get_chat_history(session_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session.id).order_by(ChatMessage.created_at.asc()).all()

    return [
        {"sender": msg.sender, "message": msg.message, "timestamp": msg.created_at.isoformat()}
        for msg in messages
    ]