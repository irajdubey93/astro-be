import httpx
from app.config import TWOFACTOR_API_KEY

VALUEFIRST_URL = "https://http.myvfirst.com/smpp/sendsms"

async def deliver_otp(phone: str, otp: str, client_name: str = "AstroApp"):

    try:
        url = f"https://2factor.in/API/V1/{TWOFACTOR_API_KEY}/SMS/{phone}/{otp}/ConsCent Live"
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(url)
            if r.json().get("Status") == "Success":
                return True
    except Exception:
        pass

    try:
        url = f"https://2factor.in/API/V1/{TWOFACTOR_API_KEY}/ADDON_SERVICES/SEND/TSMS"
        payload = {
            "From": VALUEFIRST_SENDER,
            "To": phone,
            "TemplateName": "ConsCent Live",
            "VAR1": otp,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.post(url, data=payload, headers=headers)
            if r.json().get("Status") == "Success":
                return True
    except Exception:
        pass

    raise Exception("ALL OTP PROVIDERS FAILED")
