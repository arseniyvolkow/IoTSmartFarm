from fastapi import HTTPException, Depends
from starlette import status
import abc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from jose import jwt, JWTError
import os
from passlib.context import CryptContext
from typing import Annotated
from fastapi.security import OAuth2PasswordBearer


SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable not set")

ALGORITHM = "HS256"

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
Oauth2_bearer = OAuth2PasswordBearer(tokenUrl="/api/user-service/auth/token")


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


class BaseService(abc.ABC):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self):
        pass

    async def create(self):
        pass

    async def check_access(self, entity, user_id):
        if entity.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied!"
            )

    async def update(self, entity, **kwargs):
        for key, value in kwargs.items():
            setattr(entity, key, value)
        await self.db.commit()

    async def delete(self, entity):
        await self.db.delete(entity)
        await self.db.commit()

    async def cursor_paginate(
        self,
        session,
        query,
        sort_column: str,
        cursor: Optional[str] = None,
        limit: int = 10,
    ):
        try:
            model = query.column_descriptions[0]["type"]
            try:
                sort_key = getattr(model, sort_column)
            except AttributeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid sort column: {sort_column}",
                )
            if cursor:
                query = query.filter(sort_key > cursor)

            query = query.order_by(sort_key)

            # Execute query asynchronously with the session
            result = await session.execute(query.limit(limit + 1))
            items = result.scalars().all()

            has_more = len(items) > limit
            items = items[:limit]

            if has_more:
                next_cursor = getattr(items[-1], sort_column)
            else:
                next_cursor = None

            return items, next_cursor
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Pagination error"
            )
