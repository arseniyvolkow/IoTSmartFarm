from fastapi import HTTPException
from starlette import status
from ..utils import BaseService
from ..models import Farms
from ..schemas import FarmCreate
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from typing import Optional


class FarmService(BaseService):
    async def create(self, farm: FarmCreate, user_id):
        farm_data_dict = farm.model_dump()
        farm_data_dict["user_id"] = user_id
        farm_entity = Farms(**farm_data_dict)
        self.db.add(farm_entity)
        await self.db.commit()
        return farm_entity

    async def get(self, farm_id) -> Farms:
        query = (
            select(Farms)
            .filter(Farms.farm_id == farm_id)
            .options(
                joinedload(Farms.devices), joinedload(Farms.crop_management_entries)
            )
        )
        result = await self.db.execute(query)
        farm_entity = result.unique().scalar_one_or_none() 
        if not farm_entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found"
            )
        return farm_entity

    async def get_all_farms(
        self,
        user_id: str,
        sort_column: str,
        cursor: Optional[str] = None,
        limit: Optional[int] = 10,
    ):
        query = (
        select(Farms)
        .filter(Farms.user_id == user_id)
        .options(
            # Eagerly load collections required by the FarmRead model
            joinedload(Farms.devices), 
            joinedload(Farms.crop_management_entries)
        )
    )

        items, next_cursor = await self.cursor_paginate(
            self.db, query, sort_column, cursor, limit
        )
        return items, next_cursor
