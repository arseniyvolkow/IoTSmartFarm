from farm_management_service.repositories.base_repository import BaseRepository
from farm_management_service.models import Actuators, Devices, FarmAccess
from sqlalchemy.orm import joinedload
from sqlalchemy import select, update, or_
from typing import List, Optional
from farm_management_service.schemas import ActuatorBase

class ActuatorRepository(BaseRepository):
    def add_actuators_to_session(self, device_id: str, actuators_list: List[ActuatorBase]):
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
        self.db.add_all(actuator_entities)

    async def get_by_id(self, actuator_id: str) -> Optional[Actuators]:
        query = (
            select(Actuators)
            .filter(Actuators.actuator_id == actuator_id)
            .options(joinedload(Actuators.device))
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_all_actuators(self, user_id: str, sort_column: str, cursor: Optional[str] = None, limit: int = 10):
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
        return await self.cursor_paginate(self.db, query, sort_column, cursor, limit)

    async def assign_user_to_device_actuators(self, device_id: str, user_id: str):
        query = (
            update(Actuators)
            .where(Actuators.device_id == device_id)
            .values(user_id=user_id)
        )
        await self.db.execute(query)
        await self.db.commit()
