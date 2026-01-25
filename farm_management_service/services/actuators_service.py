from farm_management_service.models import Actuators, Devices, FarmAccess
from farm_management_service.base_service import BaseService
from sqlalchemy.orm import joinedload
from sqlalchemy import select, update, or_
from typing import List, Optional, Union
from farm_management_service.schemas import ActuatorRead, ActuatorBase
from fastapi import HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from farm_management_service.database import get_db
from farm_management_service.services.access_service import AccessService
from farm_management_service.enums import AccessLevel
from common.schemas import CurrentUser


class ActuatorService(BaseService):
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

        # 2. Direct Ownership (Actuator)
        if entity.user_id == user_id:
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

    def add_actuators_to_session(
        self, device_id: str, actuators_list: List[ActuatorBase]
    ):
        """
        Creates actuator ORM objects and stages them for insertion using db.add_all().
        This method does NOT commit the transaction, leaving it to the calling service.
        """
        if not actuators_list:
            return

        actuator_entities = [
            Actuators(
                device_id=device_id,
                actuator_type=actuator.actuator_type,
                available_states=actuator.available_states,
            )
            for actuator in actuators_list
        ]
        # Use the ORM's add_all for consistency.
        self.db.add_all(actuator_entities)

    async def get(self, actuator_id: str) -> Actuators:
        query = (
            select(Actuators)
            .filter(Actuators.actuator_id == actuator_id)
            .options(joinedload(Actuators.device))
        )
        result = await self.db.execute(query)
        actuator = result.scalar_one_or_none()
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
        query = (
            select(Actuators)
            .join(Devices, Actuators.device_id == Devices.device_id)
            .outerjoin(FarmAccess, Devices.farm_id == FarmAccess.farm_id)
            .filter(
                or_(
                    Devices.user_id == user_id,
                    Actuators.user_id == user_id,
                    FarmAccess.user_id == user_id
                )
            )
            .distinct()
        )
        items, next_cursor = await self.cursor_paginate(
            self.db, query, sort_column, cursor, limit
        )
        pydantic_items = [ActuatorRead.model_validate(item) for item in items]
        return pydantic_items, next_cursor

    
    async def assign_user_to_device_actuators(self, device_id: str, user_id: str):
    # Update all actuators for this device
        query = (
            update(Actuators)
            .where(Actuators.device_id == device_id)
            .values(user_id=user_id)
        )

        await self.db.execute(query)
        await self.db.commit()