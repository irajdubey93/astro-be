from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime
import hashlib

from app.database import get_db
from app.models import User, OTP, RefreshToken
from app.utils.jwt_handler import create_access_token, create_refresh_token
from app.utils.otp_handler import generate_otp, expiry_time
from app.utils.otp_service import deliver_otp
from app.redis_client import get_redis

router = APIRouter()


# ---------------------
# Schemas
# ---------------------
class SendOTPRequest(BaseModel):
    phone: str


class VerifyOTPRequest(BaseModel):
    phone: str
    code: str


class RefreshRequest(BaseModel):
    refresh_token: str


# ---------------------
# Send OTP
# ---------------------
@router.post("/send-otp")
async def send_otp(request: Request, data: SendOTPRequest, db: Session = Depends(get_db)):
    redis = get_redis()
    ip_address = request.client.host
    phone = data.phone

    # Redis key for rate limiting (10 OTPs per 10 minutes per IP)
    key = f"otp_rate:{ip_address}"
    count = await redis.get(key)
    if count and int(count) >= 10:
        raise HTTPException(status_code=429, detail="Too many OTP requests. Try again later.")

    # Increment + set expiry in Redis
    await redis.incr(key)
    await redis.expire(key, 600)  # 10 minutes

    otp_code = generate_otp()

    # Save OTP in DB (for audit & debugging)
    otp_entry = OTP(
        phone=phone,
        code=otp_code,
        ip_address=ip_address,
        expires_at=expiry_time(),
    )
    db.add(otp_entry)
    db.commit()

    # Deliver OTP
    try:
        await deliver_otp(phone, otp_code)
        return {"status": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OTP delivery failed: {str(e)}")


# ---------------------
# Verify OTP
# ---------------------
@router.post("/verify-otp")
def verify_otp(data: VerifyOTPRequest, db: Session = Depends(get_db)):
    otp_entry = (
        db.query(OTP)
        .filter(OTP.phone == data.phone, OTP.code == data.code)
        .order_by(OTP.created_at.desc())
        .first()
    )

    if not otp_entry:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    if datetime.utcnow() > otp_entry.expires_at:
        raise HTTPException(status_code=400, detail="OTP expired")

    # Get or create user
    user = db.query(User).filter(User.phone == data.phone).first()
    if not user:
        user = User(phone=data.phone, email=f"{data.phone}@temp.local")
        db.add(user)
        db.commit()
        db.refresh(user)

    # Generate JWTs
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token_str, refresh_expiry = create_refresh_token({"sub": str(user.id)})

    # Save refresh token (hashed) in DB
    db.add(
        RefreshToken(
            user_id=user.id,
            token=hashlib.sha256(refresh_token_str.encode()).hexdigest(),
            expires_at=refresh_expiry,
        )
    )
    db.commit()

    return {"access_token": access_token, "refresh_token": refresh_token_str}


# ---------------------
# Refresh Access Token
# ---------------------
@router.post("/refresh")
def refresh_token(data: RefreshRequest, db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(data.refresh_token.encode()).hexdigest()
    rt = db.query(RefreshToken).filter(RefreshToken.token == token_hash).first()

    if not rt or datetime.utcnow() > rt.expires_at:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    access_token = create_access_token({"sub": str(rt.user_id)})
    return {"access_token": access_token}


# ---------------------
# Logout
# ---------------------
@router.post("/logout")
def logout(data: RefreshRequest, db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(data.refresh_token.encode()).hexdigest()
    deleted = db.query(RefreshToken).filter(RefreshToken.token == token_hash).delete()
    db.commit()
    if not deleted:
        raise HTTPException(status_code=400, detail="Invalid refresh token")
    return {"status": "logged_out"}