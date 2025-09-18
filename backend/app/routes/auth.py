from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models import User, OTP, RefreshToken
from app.utils.jwt_handler import create_access_token
from app.utils.otp_handler import generate_otp, expiry_time
from app.utils.otp_service import deliver_otp
from app.utils.jwt_handler import create_refresh_token
import hashlib

router = APIRouter()

# ---------------------
# Dependencies
# ---------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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
    ip_address = request.client.host

    # Rate limiting: max 10 OTPs per IP in 10 min
    ten_min_ago = datetime.utcnow() - timedelta(minutes=10)
    recent_count = db.query(OTP).filter(
        OTP.ip_address == ip_address, OTP.created_at >= ten_min_ago
    ).count()
    if recent_count >= 10:
        raise HTTPException(status_code=429, detail="Too many OTP requests. Try again later.")

    otp_code = generate_otp()
    otp_entry = OTP(
        phone=data.phone,
        code=otp_code,
        ip_address=ip_address,
        expires_at=expiry_time(),
    )
    db.add(otp_entry)
    db.commit()

    try:
        await deliver_otp(data.phone, otp_code)
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

    # Create or get user
    user = db.query(User).filter(User.phone == data.phone).first()
    if not user:
        user = User(phone=data.phone, email=f"{data.phone}@temp.local")
        db.add(user)
        db.commit()
        db.refresh(user)

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token_str, refresh_expiry = create_refresh_token({"sub": str(user.id)})

    # Save hashed refresh token
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