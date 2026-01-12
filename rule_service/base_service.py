from fastapi import HTTPException, status
import abc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime
from sqlalchemy.types import DateTime


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
        sort_column: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 10,
    ):
        try:
            model = query.column_descriptions[0]["type"]
            sort_key_name = sort_column if sort_column else "created_at"
            try:
                sort_key = getattr(model, sort_key_name)
            except AttributeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid sort column: {sort_key_name}",
                )
            if cursor:
                column_type_instance = sort_key.comparator.type
                cursor_value = cursor
                if isinstance(column_type_instance, DateTime):
                    try:
                        cursor_value = datetime.datetime.fromisoformat(cursor)
                    except ValueError:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid cursor format for DateTime column.",
                        )
                elif column_type_instance.python_type is int:
                    cursor_value = int(cursor)
                elif column_type_instance.python_type is float:
                    cursor_value = float(cursor)
                query = query.filter(sort_key > cursor_value)

            query = query.order_by(sort_key)
            result = await session.execute(query.limit(limit + 1))

            # ADD THIS LINE - Call unique() to deduplicate joined results
            items = result.unique().scalars().all()

            has_more = len(items) > limit
            items = items[:limit]

            if has_more:
                next_value = getattr(items[-1], sort_key_name)
                if isinstance(next_value, datetime.datetime):
                    next_cursor = next_value.isoformat()
                else:
                    next_cursor = str(next_value)
            else:
                next_cursor = None

            return items, next_cursor
        except Exception as e:
            print(f"Pagination failed with internal error: {e}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Pagination error"
            )
