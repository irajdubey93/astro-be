from sqlalchemy import Column, Integer, String, TIMESTAMP, func, DateTime, ForeignKey, Date, Time
from app.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100))
    email = Column(String(100), unique=True, index=True, nullable=True)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    gender = Column(String(10), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    birth_time = Column(Time, nullable=True)
    birth_place_name = Column(String(200), nullable=True)
    birth_lat = Column(String(50), nullable=True)
    birth_lon = Column(String(50), nullable=True)
    birth_tz = Column(String(20), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

class OTP(Base):
    __tablename__ = "otps"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), index=True, nullable=False)
    code = Column(String(6), nullable=False)
    ip_address = Column(String(50), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
