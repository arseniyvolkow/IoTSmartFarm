import hashlib
import os
import time
from typing import Annotated, Any

import jwt
import orjson
import redis.asyncio as redis
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError

from common.database.redis_config import is_token_blacklisted, redis_client

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable not set")

ALGORITHM = os.getenv("ALGORITHM")
if not ALGORITHM:
    raise ValueError("ALGORITHM environment variable not set")

TOKEN_URL = os.getenv("AUTH_TOKEN_URL", "http://user-service:8000/auth/token")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=TOKEN_URL)


class UserIdentity:
    """
    ULTRA-LIGHTWEIGHT IDENTITY CLASS
    --------------------------------
    Replaces Pydantic's CurrentUser for high-performance dependency injection.

    Why this instead of Pydantic?
    1. __slots__ minimizes memory usage and provides faster attribute access.
    2. Zero validation overhead: Pydantic is slow when instantiated 1000s of times/sec.
    3. Provides IDE autocompletion while remaining almost as fast as a raw dict.
    """

    __slots__ = ("access", "email", "g_perms", "id", "raw_payload", "role")

    def __init__(self, payload: dict):
        self.id = payload.get("sub")
        self.email = payload.get("email")
        self.role = payload.get("role", "guest")
        self.g_perms = payload.get("g_perms", {})
        self.access = payload.get("access", {})
        self.raw_payload = payload


def decode_access_token(token: str) -> dict:
    """
    Standard synchronous token decoding.
    Mainly used in internal logic where dependency injection isn't available.
    """
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token invalid or expired: {e}",
        )


async def get_current_user_identity(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> UserIdentity:
    """
    HIGH-PERFORMANCE AUTH DEPENDENCY
    -------------------------------
    This is the core gateway for every API request. Optimized for >500 RPS.

    Optimization Logic:
    1. REDIS SESSION CACHE: We hash the token and check Redis. If found, we skip
       expensive RSA/HMAC decoding and return the payload instantly.
    2. ORJSON: Uses Rust-based JSON parsing which is 3x faster than standard library.
    3. BLACKLIST CHECK: Only performed on cache misses to reduce Redis IO.
    4. JWT DECODE: Only performed once per token expiry session.
    """
    try:
        # Generate a fast SHA-256 hash of the token to use as a Redis key
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        cache_key = f"session:{token_hash}"

        # 1. Attempt to serve from Redis Cache (The "Fast Path")
        cached_payload = await redis_client.get(cache_key)
        if cached_payload:
            # serving from cache avoids the CPU-heavy jwt.decode
            return UserIdentity(orjson.loads(cached_payload))

        # 2. Cache Miss: Perform full cryptographic validation (The "Slow Path")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # 3. Check if token was revoked (Logout check)
        jti = payload.get("jti")
        if jti:
            if await is_token_blacklisted(jti):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked",
                )

        # 4. Cache the valid payload in Redis
        # TTL is matched exactly to the token's remaining lifespan
        exp = payload.get("exp")
        if exp:
            ttl = int(exp - time.time())
            if ttl > 0:
                await redis_client.setex(cache_key, ttl, orjson.dumps(payload))

        return UserIdentity(payload)

    except (InvalidTokenError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except redis.RedisError:
        # Fallback if Redis is down: allow requests but log the error
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication check unavailable",
        )


# Backward compatibility alias
async def get_token_payload(token: Annotated[str, Depends(oauth2_scheme)]) -> dict:
    user = await get_current_user_identity(token)
    return user.raw_payload


class CheckAccess:
    """
    RBAC PROTECTION MIDDLEWARE
    --------------------------
    Enforces Resource-based Access Control.

    Usage: Depends(CheckAccess("sensors", "write"))
    """

    def __init__(self, resource: str, action: str):
        self.resource = resource
        self.action = action

    async def __call__(
        self, user: UserIdentity = Depends(get_current_user_identity)
    ) -> UserIdentity:
        # Global admin permissions bypass specific checks
        g_perms = user.g_perms
        if self.action == "read" and g_perms.get("r_all") is True:
            return user
        if self.action in ["write", "delete"] and g_perms.get("w_all") is True:
            return user

        # Extract specific resource permissions
        access_list = user.access
        resource_access = access_list.get(self.resource)
        if not resource_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access to resource '{self.resource}' denied",
            )

        # Boolean permission check
        has_permission = False
        if self.action == "read":
            has_permission = bool(resource_access.get("r"))
        elif self.action == "write":
            has_permission = bool(resource_access.get("w"))
        elif self.action == "delete":
            has_permission = bool(resource_access.get("d"))

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not enough permissions to {self.action} {self.resource}",
            )

        return user


# --- Helpers ---


def is_admin(user: Any) -> bool:
    if isinstance(user, dict):
        return user.get("g_perms", {}).get("w_all", False)
    return getattr(user, "g_perms", {}).get("w_all", False)


def get_current_user_id(user: Any) -> str:
    if isinstance(user, dict):
        return user.get("sub")
    return getattr(user, "id", None)
