import redis.asyncio as redis
import os

# Create an async redis client
# Note: decode_responses=True converts bytes to strings automatically
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=6379,
    db=0,
    decode_responses=True
)

async def add_token_to_blacklist(jti: str, expire_seconds: int):
    async with redis_client.client() as conn:
        # Use await because this is now an async call
        await conn.setex(f"blacklist:{jti}", expire_seconds, "true")

async def is_token_blacklisted(jti: str) -> bool:
    # Use await to check existence
    exists = await redis_client.exists(f"blacklist:{jti}")
    return exists > 0