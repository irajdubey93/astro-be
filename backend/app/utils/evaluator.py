# app/evaluator.py
from google import genai
from app.config import GEMINI_API_KEY

# Gemini client
client = genai.Client(api_key=GEMINI_API_KEY)


# Fast keyword filter
def keyword_block(query: str) -> bool:
    blocked = ["suicide", "kill", "murder", "lottery", "medical diagnosis", "illegal", "terrorism"]
    return any(word in query.lower() for word in blocked)


async def llm_evaluator(query: str) -> bool:
    """
    Use Gemini to evaluate if the query is safe for astrology.
    Returns True if safe, False if unsafe.
    """

    system_prompt = """
    You are a safety evaluator for an AI astrologer chatbot.
    The chatbot should ONLY answer astrology-related questions.
    If the query is:
    - About suicide, self-harm, crime, terrorism, or illegal activities → UNSAFE.
    - A direct request for medical diagnosis or lottery prediction → UNSAFE.
    - Otherwise → SAFE.
    Respond with just "SAFE" or "UNSAFE".
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            {
                "role": "user",
                "parts": [
                    {"text": f"{system_prompt}\n\nQuery: {query}"}
                ]
            }
        ],
    )

    verdict = response.candidates[0].content.parts[0].text.strip().upper()
    return verdict == "SAFE"

async def evaluate_query(query: str) -> bool:
    """
    Main evaluator: combines keyword filter + Gemini evaluator.
    """
    if keyword_block(query):
        return False

    return await llm_evaluator(query)