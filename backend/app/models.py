from sqlalchemy import Column, String, DateTime, Date, ForeignKey, JSON, Float, Time
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from app.utils.oid import generate_oid


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_oid, index=True)
    phone = Column(String, unique=True, nullable=False)
    email = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    profiles = relationship("Profile", back_populates="user")


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(String, primary_key=True, default=generate_oid, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    full_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    phone = Column(String, unique=True, index=True, nullable=False)
    date_of_birth = Column(Date, nullable=True)
    birth_time = Column(Time, nullable=True)
    birth_place_name = Column(String, nullable=True)
    birth_lat = Column(Float, nullable=True)
    birth_lon = Column(Float, nullable=True)
    birth_tz = Column(Float, nullable=True)
    planetary_positions = Column(JSON, nullable=True)
    dasha_details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="profiles")
    sessions = relationship("ChatSession", back_populates="profile")

class OTP(Base):
    __tablename__ = "otps"

    id = Column(String, primary_key=True, default=generate_oid, index=True)
    phone = Column(String, nullable=False)
    code = Column(String, nullable=False)
    ip_address = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(String, primary_key=True, default=generate_oid, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    token = Column(String, nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, default=generate_oid, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    profile_id = Column(String, ForeignKey("profiles.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    profile = relationship("Profile", back_populates="sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, default=generate_oid, index=True)
    session_id = Column(String, ForeignKey("chat_sessions.id"), nullable=False)
    sender = Column(String, nullable=False)   # "user" or "agent"
    message = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("ChatSession", back_populates="messages")