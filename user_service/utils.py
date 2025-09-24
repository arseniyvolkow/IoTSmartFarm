from typing import Annotated
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
from .database import get_db
from passlib.context import CryptContext
from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import os
from sqlalchemy import select
from datetime import timedelta, datetime, timezone
from .models import Users


SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable not set")

ALGORITHM = "HS256"

Oauth2_bearer = OAuth2PasswordBearer(tokenUrl="auth/token")


async def get_current_user(token: Annotated[str, Depends(Oauth2_bearer)]):
    """
    Dependency function to extract user info from JWT token.
    Use this with Depends() in other routes.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, ALGORITHM)
        username: str = payload.get("username")
        user_id: int = payload.get("id")
        role: str = payload.get("role")

        if username is None or user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return {"username": username, "id": user_id, "role": role}

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )



db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]
bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def authenticate_user(username: str, password: str, db: db_dependency):
    query = select(Users).filter(Users.username == username)
    result = await db.execute(query)
    user = result.scalars().first()
    if not user:
        return False
    if not bcrypt_context.verify(password, user.hashed_password):
        return False
    return user


def create_access_token(
    username: str, user_id: int, role: str, expires_delta: timedelta
):
    encode = {"username": username, "id": user_id, "role": role}
    expires = datetime.now(timezone.utc) + expires_delta
    encode.update({"exp": expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)