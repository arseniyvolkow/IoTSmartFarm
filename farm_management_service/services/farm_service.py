from fastapi import HTTPException
from starlette import status
from farm_management_service.base_service import BaseService
from farm_management_service.models import Farms, FarmAccess
from farm_management_service.schemas import FarmCreate
from farm_management_service.services.access_service import AccessService
from farm_management_service.enums import AccessLevel
from sqlalchemy import select, or_
from sqlalchemy.orm import joinedload
from typing import Optional, Union
from common.schemas import CurrentUser


class FarmService(BaseService):
    def __init__(self, db):
        super().__init__(db)
        self.access_service = AccessService(db)

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
                joinedload(Farms.devices), 
                joinedload(Farms.crop_management_entries),
                joinedload(Farms.access_entries)
            )
        )
        result = await self.db.execute(query)
        farm_entity = result.unique().scalar_one_or_none() 
        if not farm_entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found"
            )
        return farm_entity

    async def check_access(self, entity, user: Union[CurrentUser, str], required_level: AccessLevel = AccessLevel.READ):
        """
        Overrides BaseService.check_access to support Shared Access + RBAC.
        """
        user_id = user
        
        # 1. Check Global Permissions (RBAC Override)
        if isinstance(user, CurrentUser):
            user_id = user.id
            g_perms = user.g_perms or {}
            if g_perms.get("w_all") is True:
                return # Admin Write
            if g_perms.get("r_all") is True and required_level == AccessLevel.READ:
                return # Admin Read

        # 2. Check Ownership
        if entity.user_id == user_id:
            return

        # 3. Check Shared Access
        if isinstance(entity, Farms):
            farm_id = entity.farm_id
        else:
            farm_id = getattr(entity, "farm_id", None)
        
        if farm_id:
            has_perm = await self.access_service.has_access(farm_id, user_id, required_level)
            if has_perm:
                return

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Access denied to this farm"
        )

    async def get_all_farms(
        self,
        user_id: str,
        sort_column: str,
        cursor: Optional[str] = None,
        limit: Optional[int] = 10,
    ):
        # Query farms where User is Owner OR User is in Access List
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
            .distinct() # Important because of join
        )

        items, next_cursor = await self.cursor_paginate(
            self.db, query, sort_column, cursor, limit
        )
        return items, next_cursor
