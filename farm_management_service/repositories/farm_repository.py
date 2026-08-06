
from sqlalchemy import or_, select
from sqlalchemy.orm import joinedload

from farm_management_service.models import FarmAccess, Farms
from farm_management_service.repositories.base_repository import BaseRepository


class FarmRepository(BaseRepository):
    async def create(self, farm_entity: Farms) -> Farms:
        self.db.add(farm_entity)
        await self.db.commit()
        await self.db.refresh(farm_entity)
        return farm_entity

    async def get_by_id(self, farm_id: str) -> Farms | None:
        query = (
            select(Farms)
            .filter(Farms.farm_id == farm_id)
            .options(
                joinedload(Farms.devices), 
                joinedload(Farms.crop_management_entries),
                joinedload(Farms.access_entries)
            )
        )
        result = await self.db.execute(query)
        return result.unique().scalar_one_or_none()

    async def get_all_farms(
        self,
        user_id: str,
        sort_column: str,
        cursor: str | None = None,
        limit: int = 10,
    ):
        query = (
            select(Farms)
            .outerjoin(FarmAccess, Farms.farm_id == FarmAccess.farm_id)
            .filter(
                or_(
                    Farms.user_id == user_id,
                    FarmAccess.user_id == user_id
                )
            )
            .options(
                joinedload(Farms.devices), 
                joinedload(Farms.crop_management_entries)
            )
            .distinct()
        )
        return await self.cursor_paginate(self.db, query, sort_column, cursor, limit)
