
from sqlalchemy import or_, select, update
from sqlalchemy.orm import joinedload

from farm_management_service.models import Devices, FarmAccess, Sensors
from farm_management_service.repositories.base_repository import BaseRepository
from farm_management_service.schemas import SensorBase


class SensorRepository(BaseRepository):
    def add_sensors_to_session(self, device_id: str, sensors_list: list[SensorBase]):
        if not sensors_list:
            return

        sensor_entities = [
            Sensors(
                device_id=device_id,
                sensor_type=sensor.sensor_type,
                units_of_measure=sensor.units_of_measure,
                max_value=sensor.max_value,
                min_value=sensor.min_value,
            )
            for sensor in sensors_list
        ]
        self.db.add_all(sensor_entities)

    async def get_by_id(self, sensor_id: str) -> Sensors | None:
        query = (
            select(Sensors)
            .filter(Sensors.sensor_id == sensor_id)
            .options(joinedload(Sensors.device))
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_all_sensors(self, user_id: str, sort_column: str, cursor: str | None = None, limit: int = 10):
        query = (
            select(Sensors)
            .join(Devices, Sensors.device_id == Devices.device_id)
            .outerjoin(FarmAccess, Devices.farm_id == FarmAccess.farm_id)
            .filter(
                or_(
                    Devices.user_id == user_id,
                    Sensors.user_id == user_id,
                    FarmAccess.user_id == user_id
                )
            )
            .distinct()
        )
        return await self.cursor_paginate(self.db, query, sort_column, cursor, limit)

    async def assign_user_to_device_sensors(self, device_id: str, user_id: str):
        query = (
            update(Sensors)
            .where(Sensors.device_id == device_id)
            .values(user_id=user_id)
        )
        await self.db.execute(query)
        await self.db.commit()
