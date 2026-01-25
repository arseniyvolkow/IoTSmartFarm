from typing import Dict, Union, Any
import bcrypt
import jwt
from datetime import timedelta, datetime, timezone
import os
import uuid

# Import shared configuration and validation logic
from common.security import SECRET_KEY, ALGORITHM, decode_access_token

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "20"))
REFRESH_TOKEN_EXPIRE_DAYS = 7

# bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str):
    # Convert string to bytes
    pwd_bytes = password.encode("utf-8")
    # Generate salt and hash
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    return hashed_password.decode("utf-8")


def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def create_token(
    data: Dict[str, Any],
    expires_delta: Union[timedelta, None] = None,
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
