from farm_management_service.models import Sensors, Devices
from farm_management_service.base_service import BaseService
from sqlalchemy.orm import joinedload
from sqlalchemy import select, update
from typing import List, Optional
from farm_management_service.schemas import SensorBase, SensorRead
from fastapi import HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from farm_management_service.database import get_db


class SensorService(BaseService):
    def __init__(
        self,
        db: AsyncSession = Depends(get_db),
    ):
        super().__init__(db)

    def add_sensors_to_session(self, device_id: str, sensors_list: List[SensorBase]):
        """
        Creates sensor ORM objects and stages them for insertion using db.add_all().
        This method does NOT commit the transaction.
        """
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

    async def get(self, sensor_id: str) -> Sensors:
        query = (
            select(Sensors)
            .filter(Sensors.sensor_id == sensor_id)
            .options(joinedload(Sensors.device))
        )
        result = await self.db.execute(query)
        sensor = result.scalar_one_or_none()
        if not sensor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
            )
        return sensor

    async def get_all_sensors(
        self,
        user_id: str,  # Changed from int to str to match actuator service
        sort_column: str,
        cursor: Optional[str] = None,
        limit: Optional[int] = 10,
    ) -> tuple[list[SensorRead], Optional[str]]:
        # Updated query to join with Devices to filter by user_id (same pattern as ActuatorService)
        query = (
            select(Sensors)
            .join(Devices, Sensors.device_id == Devices.device_id)
            .filter(Devices.user_id == user_id)
        )
        
        items, next_cursor = await self.cursor_paginate(
            self.db, query, sort_column, cursor, limit
        )
        
        # Convert the list of SQLAlchemy objects to a list of Pydantic models
        pydantic_items = [SensorRead.model_validate(item) for item in items]
        return pydantic_items, next_cursor


    async def assign_user_to_device_sensors(self, device_id: str, user_id: str):
        query = (
            update(Sensors)
            .where(Sensors.device_id == device_id)
            .values(user_id=user_id)
        )

        await self.db.execute(query)
        await self.db.commit()