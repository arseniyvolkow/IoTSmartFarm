from fastapi import HTTPException
from starlette import status

from common.auth.schemas import CurrentUser
from farm_management_service.enums import AccessLevel
from farm_management_service.models import CropManagement
from farm_management_service.repositories.crop_repository import CropRepository
from farm_management_service.schemas import CropManagmentCreate
from farm_management_service.services.access_service import AccessService


class CropService:
    def __init__(self, crop_repo: CropRepository, access_service: AccessService):
        self.crop_repo = crop_repo
        self.access_service = access_service

    async def check_access(
        self,
        entity,
        user: CurrentUser | str,
        required_level: AccessLevel = AccessLevel.READ,
    ):
        user_id = user

        # 1. Check Global Permissions (RBAC Override)
        if isinstance(user, CurrentUser):
            user_id = user.id
            g_perms = user.g_perms or {}
            if g_perms.get("w_all") is True:
                return  # Admin Write
            if g_perms.get("r_all") is True and required_level == AccessLevel.READ:
                return  # Admin Read

        # 2. Direct Ownership
        if entity.user_id == user_id:
            return

        # 3. Farm Access
        if entity.farm_id:
            has_perm = await self.access_service.has_access(
                entity.farm_id, user_id, required_level
            )
            if has_perm:
                return

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied!"
        )

    async def get(self, crop_id):
        crop_entity = await self.crop_repo.get_by_id(crop_id)
        if not crop_entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Crop not found"
            )
        return crop_entity

    async def create(self, crop: CropManagmentCreate, user_id: str) -> "CropManagement":
        crop_data_dict = crop.model_dump()
        crop_data_dict["user_id"] = user_id
        crop_entity = CropManagement(**crop_data_dict)
        return await self.crop_repo.create(crop_entity)

    async def assign_crop_to_farm(self, farm_entity, crop_entity):
        # FIX: Assign the farm ID to the CROP, not the other way around
        return await self.crop_repo.update(crop_entity, farm_id=farm_entity.farm_id)

    async def update(self, crop_entity: CropManagement, **kwargs) -> CropManagement:
        return await self.crop_repo.update(crop_entity, **kwargs)

    async def delete(self, crop_entity: CropManagement):
        await self.crop_repo.delete(crop_entity)
