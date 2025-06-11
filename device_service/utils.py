from fastapi import HTTPException
from starlette import status
import httpx
import abc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional


async def login_via_token(token: str):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    url_of_user_service = 'http://user_service:8005/auth/get_current_user'
    async with httpx.AsyncClient() as client:
        try:
            user_service_response = await client.get(url=url_of_user_service, headers=headers)
            if user_service_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail='Incorrect login data')
            return user_service_response.json()
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='User service unavailable!')


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
                status_code=status.HTTP_403_FORBIDDEN, detail='Access denied!'
            )

    async def update(self, entity, **kwargs):
        for key, value in kwargs.items():
            setattr(entity, key, value)
        await self.db.commit()

    async def delete(self, entity):
        await self.db.delete(entity)
        await self.db.commit()

    async def cursor_paginate(self, session, query, sort_column: str, cursor: Optional[str] = None, limit: int = 10):
        try:
            model = query.column_descriptions[0]['type']
            try:
                sort_key = getattr(model, sort_column)
            except AttributeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f'Invalid sort column: {sort_column}'
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
                status_code=status.HTTP_404_NOT_FOUND, detail='Pagination error')
