import os

import redis.asyncio as redis

# Create a connection pool for better performance under load
# max_connections prevents the system from being overwhelmed
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

pool = redis.ConnectionPool(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    db=0,
    decode_responses=True,
    max_connections=100  # Adjust based on your needs
)

# Create an async redis client using the pool
redis_client = redis.Redis(connection_pool=pool)

async def add_token_to_blacklist(jti: str, expire_seconds: int):
    # No need for manual connection management with the pool
    await redis_client.setex(f"blacklist:{jti}", expire_seconds, "true")

async def is_token_blacklisted(jti: str) -> bool:
    exists = await redis_client.exists(f"blacklist:{jti}")
    return exists > 0