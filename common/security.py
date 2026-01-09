import os
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt.exceptions import InvalidTokenError
import redis.asyncio as redis
from .redis_config import is_token_blacklisted



SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_ME_IN_PROD_SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
TOKEN_URL = os.getenv("AUTH_TOKEN_URL", "http://user-service:8000/auth/token")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=TOKEN_URL)


async def get_token_payload(token: Annotated[str, Depends(oauth2_scheme)]) -> dict:
    """
    Асинхронная зависимость:
    1. Проверяет подпись JWT (CPU).
    2. Проверяет Blacklist через redis_client (IO).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # 1. Декодируем токен
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # 2. Проверяем Blacklist (функция импортирована из redis_client.py)
        jti = payload.get("jti")
        if jti:
            # Если Redis упал, is_token_blacklisted выбросит redis.RedisError
            if await is_token_blacklisted(jti):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked"
                )
        
        return payload

    except InvalidTokenError:
        raise credentials_exception
    except redis.RedisError:
        # Ловим ошибки подключения к Redis, чтобы не крашить сервис, 
        # но и не пускать потенциально опасные запросы.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication check unavailable"
        )


class CheckAccess:
    """
    Асинхронный класс защиты.
    Использование: Depends(CheckAccess("farms", "write"))
    """
    def __init__(self, resource: str, action: str):
        self.resource = resource 
        self.action = action     

    async def __call__(self, payload: dict = Depends(get_token_payload)) -> dict:
        g_perms = payload.get("g_perms", {})
        access_list = payload.get("access", {})

        # Проверка глобальных прав
        if self.action == "read" and g_perms.get("r_all") is True:
            return payload
        if self.action in ["write", "delete"] and g_perms.get("w_all") is True:
            return payload

        # Проверка ресурса
        resource_access = access_list.get(self.resource)
        if not resource_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access to resource '{self.resource}' denied"
            )

        # Проверка действия
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
                detail=f"Not enough permissions to {self.action} {self.resource}"
            )

        return payload

# --- Helpers ---

def is_admin(payload: dict) -> bool:
    return payload.get("g_perms", {}).get("w_all", False)

def get_current_user_id(payload: dict) -> str:
    return payload.get("sub")