from sqlalchemy import (
    Column,
    String,
    TIMESTAMP,
    func,
    DateTime,
    ForeignKey,
    Date,
    Time,
    Boolean,
    Float,
    JSON
)
from sqlalchemy.orm import relationship
from app.database import Base
from app.utils.oid import generate_oid
from bson import ObjectId


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=lambda: str(ObjectId()), index=True)
    phone = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    profiles = relationship("Profile", back_populates="owner", cascade="all, delete")

class OTP(Base):
    __tablename__ = "otps"
    id = Column(String, primary_key=True, default=lambda: str(ObjectId()), index=True)
    phone = Column(String(20), index=True, nullable=False)
    code = Column(String(6), nullable=False)
    ip_address = Column(String(50), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = Column(String, primary_key=True, default=lambda: str(ObjectId()), index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(String, primary_key=True, default=lambda: str(ObjectId()), index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    full_name = Column(String, nullable=False)
    gender = Column(String(10))
    date_of_birth = Column(Date)
    birth_time = Column(Time)
    birth_place_name = Column(String)
    birth_lat = Column(Float)
    birth_lon = Column(Float)
    birth_tz = Column(Float)

    # New fields for Divine API results
    planetary_positions = Column(JSON, nullable=True)
    dasha_details = Column(JSON, nullable=True)

    owner = relationship("User", back_populates="profiles")