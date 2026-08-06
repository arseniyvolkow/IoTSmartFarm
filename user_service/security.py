import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

# Import shared configuration and validation logic
from common.auth.security import ALGORITHM, SECRET_KEY

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "20"))
REFRESH_TOKEN_EXPIRE_DAYS = 7


async def hash_password(password: str):
    """
    ASYNCHRONOUS PASSWORD HASHING
    -----------------------------
    Standard Bcrypt is synchronous and CPU-heavy (~100ms per call).
    Running it normally blocks the event loop and stops all other requests.
    
    Fix: Using asyncio.to_thread to move the computation to a worker thread.
    """
    pwd_bytes = password.encode("utf-8")
    
    def _hash():
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")
        
    return await asyncio.to_thread(_hash)


async def verify_password(plain_password: str, hashed_password: str):
    """
    ASYNCHRONOUS PASSWORD VERIFICATION
    ----------------------------------
    Prevents the event loop from freezing during login attempts.
    """
    def _verify():
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), 
            hashed_password.encode("utf-8")
        )
        
    return await asyncio.to_thread(_verify)


def create_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
    token_type: str = "access",
) -> str:
    """
    Универсальная функция для создания токена.
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Выбираем дефолтное время в зависимости от типа
        minutes = ACCESS_TOKEN_EXPIRE_MINUTES
        if token_type == "refresh":
            minutes = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60

        expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)

    # Добавляем служебные поля
    to_encode.update(
        {
            "exp": expire,
            "jti": str(uuid.uuid4()),  # Уникальный ID
            "type": token_type,  # "access" или "refresh"
        }
    )

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# Алиасы для удобства
def create_access_token(data: dict) -> str:
    return create_token(data, token_type="access")


def create_refresh_token(data: dict) -> str:
    return create_token(data, token_type="refresh")
