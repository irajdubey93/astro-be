import os
from dotenv import load_dotenv

# Load from .env (if exists)
load_dotenv()

# -----------------------------
# Database Config
# -----------------------------
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "astrodb")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")  # ✅ Docker service name
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

DATABASE_URL = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@"
    f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

# -----------------------------
# Redis Config
# -----------------------------
REDIS_HOST = os.getenv("REDIS_HOST", "redis")  # ✅ Docker service name
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

# -----------------------------
# JWT Config
# -----------------------------
JWT_SECRET = os.getenv("JWT_SECRET", "supersecret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# -----------------------------
# External APIs
# -----------------------------
DIVINE_API_KEY = os.getenv("DIVINE_API_KEY", "")
DIVINE_AUTH_TOKEN = os.getenv("DIVINE_AUTH_TOKEN", "")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

TWOFACTOR_API_KEY = os.getenv("TWOFACTOR_API_KEY")