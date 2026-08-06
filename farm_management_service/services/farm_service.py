from fastapi import HTTPException
from starlette import status

from common.auth.schemas import CurrentUser
from farm_management_service.enums import AccessLevel
from farm_management_service.models import Farms
from farm_management_service.repositories.farm_repository import FarmRepository
from farm_management_service.schemas import FarmCreate
from farm_management_service.services.access_service import AccessService


class FarmService:
    def __init__(self, farm_repo: FarmRepository, access_service: AccessService):
        self.farm_repo = farm_repo
        self.access_service = access_service

    async def create(self, farm: FarmCreate, user_id: str) -> Farms:
        farm_data_dict = farm.model_dump()
        farm_data_dict["user_id"] = user_id
        farm_entity = Farms(**farm_data_dict)
        return await self.farm_repo.create(farm_entity)

    async def get(self, farm_id: str) -> Farms:
        farm_entity = await self.farm_repo.get_by_id(farm_id)
        if not farm_entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found"
            )
        return farm_entity

    async def check_access(
        self,
        entity,
        user: CurrentUser | str,
        required_level: AccessLevel = AccessLevel.READ,
    ):
        """
        Overrides BaseService.check_access to support Shared Access + RBAC.
        """
        user_id = user

        # 1. Check Global Permissions (RBAC Override)
        if isinstance(user, CurrentUser):
            user_id = user.id
            g_perms = user.g_perms or {}
            if g_perms.get("w_all") is True:
                return  # Admin Write
            if g_perms.get("r_all") is True and required_level == AccessLevel.READ:
                return  # Admin Read

        # 2. Check Ownership
        if entity.user_id == user_id:
            return

        # 3. Check Shared Access
        if isinstance(entity, Farms):
            farm_id = entity.farm_id
        else:
            farm_id = getattr(entity, "farm_id", None)

        if farm_id:
            has_perm = await self.access_service.has_access(
                farm_id, user_id, required_level
            )
            if has_perm:
                return

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this farm"
        )

    async def get_all_farms(
        self,
        user_id: str,
        sort_column: str,
        cursor: str | None = None,
        limit: int = 10,
    ):
        return await self.farm_repo.get_all_farms(user_id, sort_column, cursor, limit)

    async def update(self, farm_entity: Farms, **kwargs) -> Farms:
        return await self.farm_repo.update(farm_entity, **kwargs)

    async def delete(self, farm_entity: Farms):
        await self.farm_repo.delete(farm_entity)
