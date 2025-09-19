import redis.asyncio as redis
from app.config import REDIS_URL

# Global Redis client (initialized at startup)
redis_client: redis.Redis | None = None


async def init_redis():
    """Initialize Redis connection at app startup."""
    global redis_client
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    try:
        await redis_client.ping()
        print("✅ Connected to Redis")
    except Exception as e:
        print(f"❌ Failed to connect to Redis: {e}")
        redis_client = None


async def close_redis():
    """Close Redis connection at app shutdown."""
    global redis_client
    if redis_client:
        await redis_client.close()
        print("🛑 Redis connection closed")


def get_redis() -> redis.Redis:
    """Return active Redis client (used in routes)."""
    if not redis_client:
        raise RuntimeError("Redis client is not initialized")
    return redis_client