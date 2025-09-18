import httpx
from app.config import DIVINE_API_KEY, DIVINE_AUTH_TOKEN

BASE_URL = "https://astroapi-3.divineapi.com/indian-api/v1"

async def fetch_divine_data(profile):
    payload = {
        "api_key": DIVINE_API_KEY,
        "full_name": profile.full_name,
        "day": profile.date_of_birth.day,
        "month": profile.date_of_birth.month,
        "year": profile.date_of_birth.year,
        "hour": profile.birth_time.hour,
        "min": profile.birth_time.minute,
        "sec": 0,
        "gender": profile.gender,
        "place": profile.birth_place_name,
        "lat": profile.birth_lat,
        "lon": profile.birth_lon,
        "tzone": profile.birth_tz,
        "lan": "en",
        "dasha_type": "antar-dasha",
    }

    headers = {"Authorization": f"Bearer {DIVINE_AUTH_TOKEN}"}

    async with httpx.AsyncClient() as client:
        planetary = await client.post(f"{BASE_URL}/planetary-positions", headers=headers, data=payload)
        dasha = await client.post(f"{BASE_URL}/vimshottari-dasha", headers=headers, data=payload)

    return {
        "planetary_positions": planetary.json() if planetary.status_code == 200 else None,
        "dasha_details": dasha.json() if dasha.status_code == 200 else None,
    }