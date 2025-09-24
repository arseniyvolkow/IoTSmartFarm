from ..models import Sensors
from ..utils import BaseService
from sqlalchemy.orm import joinedload
from sqlalchemy import select, insert
from typing import List, Optional
from ..schemas import SensorBase, SensorRead
from fastapi import HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db

class SensorService(BaseService):
    def __init__(
        self,
        db: AsyncSession = Depends(get_db),
    ):
        super().__init__(db)


    def add_sensors_to_session(
        self, device_id: str, sensors_list: List[SensorBase]
    ):
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

    async def get(self, device_id: str) -> SensorRead:
        query = (
            select(Sensors)
            .filter(Sensors.unique_device_id == device_id)
            .options(joinedload(Sensors.device))
        )
        result = await self.db.execute(query)
        sensor = result.scalar_one_or_none()
        if not sensor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
            )
        return SensorRead.model_validate(sensor)

    async def get_all_sensors(
        self,
        user_id: int,
        sort_column: str,
        cursor: Optional[str] = None,
        limit: Optional[int] = 10,
    ) -> tuple[list[SensorRead], Optional[str]]:
        # This query is correct because it selects from the Sensors model
        query = select(Sensors).filter(Sensors.user_id == user_id)

        items, next_cursor = await self.cursor_paginate(
            self.db, query, sort_column, cursor, limit
        )

        # Convert the list of SQLAlchemy objects to a list of Pydantic models
        # Use a list comprehension for efficient conversion
        pydantic_items = [SensorRead.model_validate(item) for item in items]

        return pydantic_items, next_cursor
