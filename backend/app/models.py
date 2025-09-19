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
    full_name = Column(String, nullable=True)   # Optional now
    email = Column(String, nullable=True)       # ✅ Added optional email
    gender = Column(String, nullable=True)      # Optional now
    phone = Column(String, nullable=True)       # ✅ Store phone if needed
    date_of_birth = Column(Date, nullable=True) # ✅ Changed to Date
    birth_time = Column(Time, nullable=True)    # ✅ Matches schema
    birth_place_name = Column(String, nullable=True)
    birth_lat = Column(Float, nullable=True)
    birth_lon = Column(Float, nullable=True)
    birth_tz = Column(Float, nullable=True)
    planetary_positions = Column(JSON, nullable=True)
    dasha_details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="profiles")


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