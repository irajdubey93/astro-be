# app/utils/divine_api.py
import json
import httpx
from app.config import DIVINE_API_KEY, DIVINE_AUTH_TOKEN
from app.redis_client import get_redis

BASE_URL = "https://astroapi-3.divineapi.com/indian-api/v1"


async def fetch_divine_data(profile):
    """
    Fetch planetary positions + dasha details for a profile.
    Uses Redis cache for optimization (6 hours).
    """
    redis = get_redis()
    cache_key = f"astro:{profile.id}"

    # ✅ Try cache first
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    # ✅ Build payload for API
    payload = {
        "api_key": DIVINE_API_KEY,
        "full_name": profile.full_name,
        "day": profile.date_of_birth.day,
        "month": profile.date_of_birth.month,
        "year": profile.date_of_birth.year,
        "hour": profile.birth_time.hour if profile.birth_time else 0,
        "min": profile.birth_time.minute if profile.birth_time else 0,
        "sec": 0,
        "gender": (profile.gender or "").lower(),
        "place": profile.birth_place_name,
        "lat": profile.birth_lat,
        "lon": profile.birth_lon,
        "tzone": profile.birth_tz,
        "lan": "en",
        "dasha_type": "antar-dasha",
    }

    headers = {"Authorization": f"Bearer {DIVINE_AUTH_TOKEN}"}

    async with httpx.AsyncClient(timeout=30) as client:
        planetary = await client.post(
            f"{BASE_URL}/planetary-positions", headers=headers, data=payload
        )
        dasha = await client.post(
            f"{BASE_URL}/vimshottari-dasha", headers=headers, data=payload
        )

    result = {
        "planetary_positions": (
            planetary.json() if planetary.status_code == 200 else None
        ),
        "dasha_details": dasha.json() if dasha.status_code == 200 else None,
    }

    # ✅ Save in Redis for 6 hours
    await redis.setex(cache_key, 21600, json.dumps(result))

    return result