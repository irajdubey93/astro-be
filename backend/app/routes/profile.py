# backend/app/routes/profile.py

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field, validator

from datetime import datetime
import httpx
import re
from typing import Annotated
from datetime import date, time



from app.database import SessionLocal
from app.models import User
from app.utils.jwt_handler import verify_access_token
from app.config import GOOGLE_MAPS_API_KEY

router = APIRouter()

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

class ProfileRequest(BaseModel):
    full_name: Annotated[str | None, Field(min_length=2, max_length=100)] = None
    email: EmailStr | None = None
    gender: str | None = None
    phone: Annotated[str | None, Field(pattern=r"^\+?[0-9]{10,15}$")] = None
    date_of_birth: date | None = None
    birth_time: time | None = None
    birth_place_name: str | None = None
    birth_lat: str | None = None
    birth_lon: str | None = None
    birth_tz: str | None = None

@router.patch("/profile")
def patch_profile(data: ProfileRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    for field, value in data.dict(exclude_unset=True).items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return current_user

@router.post("/profile")
def update_profile(data: ProfileRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if data.full_name: current_user.full_name = data.full_name
    if data.email: current_user.email = data.email
    if data.phone: current_user.phone = data.phone
    if data.date_of_birth: current_user.date_of_birth = data.date_of_birth
    if data.birth_time: current_user.birth_time = str(data.birth_time)
    if data.birth_place_name: current_user.birth_place_name = data.birth_place_name
    if data.birth_lat: current_user.birth_lat = data.birth_lat
    if data.birth_lon: current_user.birth_lon = data.birth_lon
    if data.birth_tz: current_user.birth_tz = data.birth_tz
    if data.gender: current_user.gender = data.gender

    db.commit()
    db.refresh(current_user)
    return current_user

@router.get("/profile/me")
def get_profile(current_user: User = Depends(get_current_user)):
    return current_user

# --- Google Maps Autocomplete ---
@router.get("/profile/search-location")
async def search_location(query: str,current_user: User = Depends(get_current_user)):
    url = f"https://maps.googleapis.com/maps/api/place/autocomplete/json"
    params = {"input": query, "key": GOOGLE_MAPS_API_KEY}
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params)
        return r.json()

# --- Select location and fetch lat/lon/tz ---
@router.get("/profile/select-location")
async def select_location(place_id: str,current_user: User = Depends(get_current_user)):
    # Get lat/lon
    geo_url = f"https://maps.googleapis.com/maps/api/geocode/json"
    async with httpx.AsyncClient() as client:
        geo = await client.get(geo_url, params={"place_id": place_id, "key": GOOGLE_MAPS_API_KEY})
        geo_data = geo.json()
        if not geo_data["results"]:
            raise HTTPException(status_code=400, detail="Invalid place_id")

        location = geo_data["results"][0]["geometry"]["location"]
        name = geo_data["results"][0]["formatted_address"]

        lat = location["lat"]
        lon = location["lng"]

        # Get timezone
        tz_url = "https://maps.googleapis.com/maps/api/timezone/json"
        tz = await client.get(tz_url, params={"location": f"{lat},{lon}", "timestamp": int(datetime.utcnow().timestamp()), "key": GOOGLE_MAPS_API_KEY})
        tz_data = tz.json()

        return {
            "place_name": name,
            "lat": lat,
            "lon": lon,
            "timezone": tz_data.get("rawOffset", 0) / 3600  # convert seconds to hours
        }