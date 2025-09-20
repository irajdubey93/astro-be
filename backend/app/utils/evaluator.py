# app/evaluator.py
from datetime import datetime, timedelta
from dateutil import parser as date_parser
import re
from google import genai
from app.config import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)

# ------------------------
# Input Guardrails
# ------------------------
BLOCKED_KEYWORDS = [
    "suicide", "kill", "murder", "terrorism", "illegal",
    "hack", "weapon", "drugs", "lottery", "diagnosis"
]

ALLOWED_AREAS = [
    "career", "job", "promotion", "demotion", "startup",
    "marriage", "relationship", "children", "pregnancy",
    "family", "finance", "wealth", "income", "business",
    "education", "future", "health", "success", "failure",
    "spirituality", "remedies", "guidance", "fortune"
]


def keyword_block(query: str) -> bool:
    """Block if query contains unsafe keywords."""
    return any(word in query.lower() for word in BLOCKED_KEYWORDS)


async def evaluate_query(query: str) -> bool:
    """
    Validate if query is astrology-safe.
    Blocks unsafe content, allows life/astrology queries.
    """
    if keyword_block(query):
        return False

    system_prompt = """
    You are a safety evaluator for an AI astrologer chatbot.
    Rules:
    - If about suicide, self-harm, terrorism, illegal activity, hacking, or drugs → UNSAFE.
    - If asking for medical diagnosis or lottery prediction → UNSAFE.
    - If related to career, marriage, children, relationships, finance, family, spirituality, remedies, or astrology → SAFE.
    Respond only with SAFE or UNSAFE.
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[{"role": "user", "parts": [{"text": f"{system_prompt}\n\nQuery: {query}"}]}],
    )
    verdict = response.candidates[0].content.parts[0].text.strip().upper()
    return verdict == "SAFE"


# ------------------------
# Output Guardrails
# ------------------------
async def evaluate_output(answer: str) -> bool:
    """Check if AI output is valid astrology response."""
    eval_prompt = f"""
    You are an evaluator. Judge if the following response is a valid astrology-based answer.

    Rules:
    - Must reference Grahas (planets), Rashis (signs), Bhavas (houses), or Dasha/Antardasha periods.
    - Cannot be generic like "Good times ahead".
    - Must be rooted in astrology logic, not vague advice.

    Response:
    {answer}

    Reply with SAFE or UNSAFE only.
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[{"role": "user", "parts": [{"text": eval_prompt}]}],
    )
    verdict = response.candidates[0].content.parts[0].text.strip().upper()
    return verdict == "SAFE"


# ------------------------
# Date Extraction for Query
# ------------------------
async def extract_reference_date(query: str) -> str | None:
    """
    Extract a reference date from user query.
    - If mentions explicit date/month/year → return that date.
    - If mentions "next X days/weeks/months" → calculate from today.
    - Else return None (default to today).
    """
    today = datetime.utcnow()

    # Try explicit date
    try:
        parsed = date_parser.parse(query, fuzzy=True, default=today)
        if parsed.date() != today.date():
            return parsed.strftime("%Y-%m-%d")
    except Exception:
        pass

    # Relative expressions
    rel_match = re.search(r"next (\d+) (day|week|month|year)s?", query.lower())
    if rel_match:
        num = int(rel_match.group(1))
        unit = rel_match.group(2)

        if unit == "day":
            ref = today + timedelta(days=num)
        elif unit == "week":
            ref = today + timedelta(weeks=num)
        elif unit == "month":
            ref = today + timedelta(days=num * 30)
        elif unit == "year":
            ref = today + timedelta(days=num * 365)
        else:
            ref = today

        return ref.strftime("%Y-%m-%d")

    return None