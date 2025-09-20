# app/routes/profile.py
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, date, time
from typing import Optional, Annotated, List
import httpx, json

from app.database import get_db
from app.models import User, Profile
from app.utils.jwt_handler import verify_access_token
from app.utils.divine_api import fetch_divine_data
from app.config import GOOGLE_MAPS_API_KEY


router = APIRouter()


# ---------------------
# Auth Helper
# ---------------------
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
# Schemas
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


class ProfileResponse(BaseModel):
    id: str
    user_id: str
    full_name: Optional[str]
    email: Optional[str]
    gender: Optional[str]
    phone: Optional[str]
    date_of_birth: Optional[date]
    birth_time: Optional[time]
    birth_place_name: Optional[str]
    birth_lat: Optional[float]
    birth_lon: Optional[float]
    birth_tz: Optional[float]
    planetary_positions: Optional[dict]
    dasha_details: Optional[dict]

    class Config:
        from_attributes = True  # ✅ Pydantic v2 fix


# ---------------------
# Helpers
# ---------------------
def serialize_profile(profile: Profile) -> ProfileResponse:
    planetary_positions = (
        json.loads(profile.planetary_positions)
        if profile.planetary_positions else None
    )
    dasha_details = (
        json.loads(profile.dasha_details)
        if profile.dasha_details else None
    )
    return ProfileResponse(
        id=str(profile.id),
        user_id=str(profile.user_id),
        full_name=profile.full_name,
        email=profile.email,
        gender=profile.gender,
        phone=profile.phone,
        date_of_birth=profile.date_of_birth,  # ✅ FIXED
        birth_time=profile.birth_time,
        birth_place_name=profile.birth_place_name,
        birth_lat=profile.birth_lat,
        birth_lon=profile.birth_lon,
        birth_tz=profile.birth_tz,
        planetary_positions=planetary_positions,
        dasha_details=dasha_details,
    )

# ---------------------
# CRUD Endpoints
# ---------------------

@router.post("/profiles", response_model=ProfileResponse)
async def create_profile(
    data: ProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = Profile(user_id=current_user.id, **data.dict(exclude_unset=True))
    db.add(profile)
    db.commit()
    db.refresh(profile)

    # 🔮 Fetch Divine data (safe, cached, with fallback)
    divine_data = await fetch_divine_data(profile)
    profile.planetary_positions = json.dumps(divine_data.get("planetary_positions", {}))
    profile.dasha_details = json.dumps(divine_data.get("dasha_details", {}))
    db.commit()
    db.refresh(profile)

    return serialize_profile(profile)


@router.get("/profiles", response_model=List[ProfileResponse])
def list_profiles(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    profiles = db.query(Profile).filter(Profile.user_id == current_user.id).all()
    return [serialize_profile(p) for p in profiles]



# ---------------------
# Google Maps Helpers
# ---------------------

@router.get("/profiles/search-location")
async def search_location(query: str, current_user: User = Depends(get_current_user)):
    url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
    params = {"input": query, "key": GOOGLE_MAPS_API_KEY}
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params)
        return r.json()


@router.get("/profiles/select-location")
async def select_location(
    place_id: str, current_user: User = Depends(get_current_user)
):
    geo_url = "https://maps.googleapis.com/maps/api/geocode/json"
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



@router.get("/profiles/{profile_id}", response_model=ProfileResponse)
def get_profile(
    profile_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = db.query(Profile).filter(
        Profile.id == profile_id, Profile.user_id == current_user.id
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    return serialize_profile(profile)


@router.patch("/profiles/{profile_id}", response_model=ProfileResponse)
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

    for field, value in data.dict(exclude_unset=True).items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)

    # 🔮 Re-fetch Divine data after update
    divine_data = await fetch_divine_data(profile)
    profile.planetary_positions = json.dumps(divine_data.get("planetary_positions", {}))
    profile.dasha_details = json.dumps(divine_data.get("dasha_details", {}))
    db.commit()
    db.refresh(profile)

    return serialize_profile(profile)


@router.delete("/profiles/{profile_id}")
def delete_profile(
    profile_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = db.query(Profile).filter(
        Profile.id == profile_id, Profile.user_id == current_user.id
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    db.delete(profile)
    db.commit()
    return {"status": "deleted"}

# ---------------------
# Refresh Divine Data Manually
# ---------------------
@router.post("/profiles/{profile_id}/refresh-astro-data", response_model=ProfileResponse)
async def refresh_astro_data(
    profile_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = db.query(Profile).filter(
        Profile.id == profile_id, Profile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    divine_data = await fetch_divine_data(profile)
    profile.planetary_positions = json.dumps(divine_data.get("planetary_positions", {}))
    profile.dasha_details = json.dumps(divine_data.get("dasha_details", {}))
    db.commit()
    db.refresh(profile)

    return serialize_profile(profile)