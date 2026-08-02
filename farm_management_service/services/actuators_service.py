from farm_management_service.models import Actuators
from typing import List, Optional, Union
from farm_management_service.schemas import ActuatorRead, ActuatorBase
from fastapi import HTTPException, status
from farm_management_service.services.access_service import AccessService
from farm_management_service.repositories.actuator_repository import ActuatorRepository
from farm_management_service.enums import AccessLevel
from common.schemas import CurrentUser


class ActuatorService:
    def __init__(self, actuator_repo: ActuatorRepository, access_service: AccessService):
        self.actuator_repo = actuator_repo
        self.access_service = access_service

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

        # 2. Direct Ownership (Actuator)
        if getattr(entity, "user_id", None) == user_id:
            return
            
        # 3. Device Ownership
        if entity.device and entity.device.user_id == user_id:
            return

        # 4. Farm Access
        device = entity.device
        if device and device.farm_id:
            has_perm = await self.access_service.has_access(device.farm_id, user_id, required_level)
            if has_perm:
                return

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied!"
        )

    def add_actuators_to_session(self, device_id: str, actuators_list: List[ActuatorBase]):
        self.actuator_repo.add_actuators_to_session(device_id, actuators_list)

    async def get(self, actuator_id: str) -> Actuators:
        actuator = await self.actuator_repo.get_by_id(actuator_id)
        if not actuator:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Actuator not found"
            )
        return actuator

    async def get_all_actuators(
        self,
        user_id: str,
        sort_column: str,
        cursor: Optional[str] = None,
        limit: Optional[int] = 10,
    ) -> tuple[list[ActuatorRead], Optional[str]]:
        items, next_cursor = await self.actuator_repo.get_all_actuators(user_id, sort_column, cursor, limit)
        pydantic_items = [ActuatorRead.model_validate(item) for item in items]
        return pydantic_items, next_cursor

    async def assign_user_to_device_actuators(self, device_id: str, user_id: str):
        await self.actuator_repo.assign_user_to_device_actuators(device_id, user_id)

    async def update(self, actuator_entity: Actuators, **kwargs) -> Actuators:
        return await self.actuator_repo.update(actuator_entity, **kwargs)

    async def delete(self, actuator_entity: Actuators):
        await self.actuator_repo.delete(actuator_entity)