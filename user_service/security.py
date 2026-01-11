from typing import  Dict, Union, Any 
from fastapi import  HTTPException, status
import jwt
from datetime import timedelta, datetime, timezone
import os
from passlib.context import CryptContext
import uuid
from jwt.exceptions import PyJWTError

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable not set")

ALGORITHM = os.getenv("ALGORITHM")
if not ALGORITHM:
    raise ValueError("ALGORITHM environment variable not set")

ACCESS_TOKEN_EXPIRE_MINUTES = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")
if not ACCESS_TOKEN_EXPIRE_MINUTES:
    ACCESS_TOKEN_EXPIRE_MINUTES = 20

REFRESH_TOKEN_EXPIRE_DAYS = 7 

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password):
    return bcrypt_context.hash(password)


def verify_password(plain_password, hashed_password):
    return bcrypt_context.verify(plain_password, hashed_password)


def create_token(
    data: Dict[str, Any], 
    expires_delta: Union[timedelta, None] = None,
    token_type: str = "access"
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
    to_encode.update({
        "exp": expire,
        "jti": str(uuid.uuid4()), # Уникальный ID
        "type": token_type        # "access" или "refresh"
    })

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        # This will automatically check 'exp' for you
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token invalid or expired: {e}",
        )
    

# Алиасы для удобства
def create_access_token(data: dict) -> str:
    return create_token(data, token_type="access")

def create_refresh_token(data: dict) -> str:
    return create_token(data, token_type="refresh")