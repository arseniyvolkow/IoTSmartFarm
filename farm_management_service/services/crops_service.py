from fastapi import HTTPException, Depends
from starlette import status
from farm_management_service.base_service import BaseService
from farm_management_service.models import CropManagement
from sqlalchemy import select
from farm_management_service.schemas import CropManagmentCreate
from sqlalchemy.ext.asyncio import AsyncSession
from farm_management_service.database import get_db
from farm_management_service.services.access_service import AccessService
from farm_management_service.enums import AccessLevel
from typing import Union
from common.schemas import CurrentUser


class CropService(BaseService):
    def __init__(
        self,
        db: AsyncSession = Depends(get_db),
    ):
        super().__init__(db)
        self.access_service = AccessService(db)

    async def check_access(self, entity, user: Union[CurrentUser, str], required_level: AccessLevel = AccessLevel.READ):
        user_id = user
        
        # 1. Check Global Permissions (RBAC Override)
        if isinstance(user, CurrentUser):
            user_id = user.id
            g_perms = user.g_perms or {}
            if g_perms.get("w_all") is True:
                return # Admin Write
            if g_perms.get("r_all") is True and required_level == AccessLevel.READ:
                return # Admin Read

        # 2. Direct Ownership
        if entity.user_id == user_id:
            return

        # 3. Farm Access
        if entity.farm_id:
            has_perm = await self.access_service.has_access(entity.farm_id, user_id, required_level)
            if has_perm:
                return

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied!"
        )

    async def get(self, crop_id):
        query = select(CropManagement).filter(CropManagement.crop_id == crop_id)
        result = await self.db.execute(query)
        crop_entity = result.scalar_one_or_none()
        if not crop_entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Crop not found"
            )
        return crop_entity

    async def create(self, crop: CropManagmentCreate, user_id: str) -> "CropManagement":
        crop_data_dict = crop.model_dump()
        crop_data_dict["user_id"] = user_id
        crop_entity = CropManagement(**crop_data_dict)
        self.db.add(crop_entity)
        await self.db.commit()
        return crop_entity

    async def assign_crop_to_farm(self, farm_entity, crop_entity):
        # FIX: Assign the farm ID to the CROP, not the other way around
        crop_entity.farm_id = farm_entity.farm_id
        await self.db.commit()
        return crop_entity
