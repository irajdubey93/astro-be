from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from datetime import datetime
import json

from app.database import get_db
from app.models import ChatSession, ChatMessage, Profile, User
from app.utils.jwt_handler import verify_access_token
from app.ai.chat_agent import generate_response
from app.redis_client import get_redis

router = APIRouter()

# 🔑 Authentication Helper
def get_current_user(authorization: str = Header(...), db: Session = Depends(get_db)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization.split(" ")[1]
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# --------------------
# Start Chat Session
# --------------------
@router.post("/chat/start/{profile_id}")
def start_chat(profile_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    profile = db.query(Profile).filter(Profile.id == profile_id, Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    session = ChatSession(user_id=current_user.id, profile_id=profile.id)
    db.add(session)
    db.commit()
    db.refresh(session)

    return {"session_id": session.id, "message": "Chat session started"}

# --------------------
# Send Message
# --------------------
@router.post("/chat/{session_id}/send")
async def send_message(session_id: str, query: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    profile = db.query(Profile).filter(Profile.id == session.profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    answer = await generate_response(db, session, profile, query)
    return {"user": query, "agent": answer}

# --------------------
# Get Chat History
# --------------------
@router.get("/chat/{session_id}/history")
async def get_history(session_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    redis_conn = await get_redis()
    messages_key = f"chat:messages:{session_id}"

    # Prefer Redis (faster)
    history = await redis_conn.lrange(messages_key, 0, -1)
    if history:
        return [json.loads(msg) for msg in history]

    # Fallback to DB
    msgs = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at).all()
    return [{"role": msg.sender, "content": msg.message} for msg in msgs]