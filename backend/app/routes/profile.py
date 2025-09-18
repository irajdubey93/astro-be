# app/routes/profile.py
from fastapi import APIRouter, Depends, HTTPException, Header, Path
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, date, time
import httpx

from typing import Optional, Annotated
from app.database import SessionLocal
from app.models import User, Profile
from app.utils.jwt_handler import verify_access_token
from app.config import GOOGLE_MAPS_API_KEY
from app.utils.divine_api import fetch_divine_data


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

# ---------------------
# Request Schema
# ---------------------
class ProfileRequest(BaseModel):
    full_name: Annotated[Optional[str], Field(min_length=2, max_length=100)] = None
    email: Optional[EmailStr] = None
    gender: Optional[str] = None
    phone: Annotated[Optional[str], Field(pattern=r"^\+?[0-9]{10,15}$")] = None
    date_of_birth: Optional[date] = None
    birth_time: Optional[time] = None
    birth_place_name: Optional[str] = None
    birth_lat: Optional[float] = None
    birth_lon: Optional[float] = None
    birth_tz: Optional[float] = None

# ---------------------
# CRUD Endpoints
# ---------------------

@router.post("/profiles")
async def create_profile(
    data: ProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = Profile(
        user_id=current_user.id,
        full_name=data.full_name,
        gender=data.gender,
        date_of_birth=data.date_of_birth,
        birth_time=data.birth_time,
        birth_place_name=data.birth_place_name,
        birth_lat=data.birth_lat,
        birth_lon=data.birth_lon,
        birth_tz=data.birth_tz,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    # 🔮 Fetch Divine data and update profile
    divine_data = await fetch_divine_data(profile)
    profile.planetary_positions = divine_data["planetary_positions"]
    profile.dasha_details = divine_data["dasha_details"]
    db.commit()
    db.refresh(profile)

    return profile

@router.get("/profiles")
def list_profiles(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return db.query(Profile).filter(Profile.user_id == current_user.id).all()


@router.get("/profiles/{profile_id}")
def get_profile(
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
    return profile


@router.patch("/profiles/{profile_id}")
async def patch_profile(
    profile_id: str,
    data: ProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = db.query(Profile).filter(
        Profile.id == profile_id, Profile.user_id == current_user.id
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Apply only provided fields
    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)

    # 🔮 Re-fetch Divine data after update
    divine_data = await fetch_divine_data(profile)
    profile.planetary_positions = divine_data["planetary_positions"]
    profile.dasha_details = divine_data["dasha_details"]
    db.commit()
    db.refresh(profile)

    return profile

@router.delete("/profiles/{profile_id}")
def delete_profile(
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

    db.delete(profile)
    db.commit()
    return {"status": "deleted"}

# ---------------------
# Google Maps Helpers
# ---------------------

@router.get("/profiles/search-location")
async def search_location(
    query: str, current_user: User = Depends(get_current_user)
):
    url = f"https://maps.googleapis.com/maps/api/place/autocomplete/json"
    params = {"input": query, "key": GOOGLE_MAPS_API_KEY}
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params)
        return r.json()


@router.get("/profiles/select-location")
async def select_location(
    place_id: str, current_user: User = Depends(get_current_user)
):
    geo_url = f"https://maps.googleapis.com/maps/api/geocode/json"
    async with httpx.AsyncClient() as client:
        geo = await client.get(
            geo_url, params={"place_id": place_id, "key": GOOGLE_MAPS_API_KEY}
        )
        geo_data = geo.json()
        if not geo_data["results"]:
            raise HTTPException(status_code=400, detail="Invalid place_id")

        location = geo_data["results"][0]["geometry"]["location"]
        name = geo_data["results"][0]["formatted_address"]

        lat = location["lat"]
        lon = location["lng"]

        tz_url = "https://maps.googleapis.com/maps/api/timezone/json"
        tz = await client.get(
            tz_url,
            params={
                "location": f"{lat},{lon}",
                "timestamp": int(datetime.utcnow().timestamp()),
                "key": GOOGLE_MAPS_API_KEY,
            },
        )
        tz_data = tz.json()

        return {
            "place_name": name,
            "lat": lat,
            "lon": lon,
            "timezone": tz_data.get("rawOffset", 0) / 3600,
        }