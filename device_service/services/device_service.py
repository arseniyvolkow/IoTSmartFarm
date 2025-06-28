from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from starlette import status
from ..models import Devices, Sensors, Farms
from ..utils import BaseService
from sqlalchemy import select
from ..schemas import AddNewDevice
from sqlalchemy.orm import joinedload
from typing import Optional


class DeviceService(BaseService):
    """
    A service class for managing device-related operations.

    Methods:
        get(device_id: str):
            Retrieves a device by its unique ID.
        create(user_id: int, device_data: AddNewDevice):
            Creates a new device and its associated sensors.
    """

    async def get(self, device_id: str) -> Devices:
        query = (
            select(Devices)
            .filter(Devices.unique_device_id == device_id)
            .options(joinedload(Devices.sensors))
        )
        result = await self.db.execute(query)
        device = result.scalar_one_or_none()
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
            )
        return device

    async def create(self, user_id, device_data: AddNewDevice) -> Devices:
        query = select(Devices).filter(
            Devices.unique_device_id == device_data.unique_device_id
        )
        result = await self.db.execute(query)
        existing_device = result.scalar_one_or_none()
        if existing_device:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Device already exists!"
            )
        device_entity = Devices(
            unique_device_id=device_data.unique_device_id,
            user_id=user_id,
            device_ip_address=device_data.device_ip_address,
            model_number=device_data.model_number,
            firmware_version=device_data.firmware_version,
            status="inactive",
        )
        try:
            self.db.add(device_entity)
            await self.db.flush()
            sensor_entities = [
                Sensors(
                    device_id=device_entity.unique_device_id,
                    sensor_type=sensor.sensor_type,
                    units_of_measure=sensor.units_of_measure,
                    max_value=sensor.max_value,
                    min_value=sensor.min_value,
                )
                for sensor in device_data.sensors_list
            ]

            self.db.bulk_save_objects(sensor_entities)
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Device with this unique ID already exists (DB constraint error).",
            )
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error: {str(e)}",
            )
        return device_entity

    async def get_unassigned_devices(
        self,
        user_id: int,
        sort_column: str,
        cursor: Optional[str] = None,
        limit: Optional[int] = 10,
    ):
        query = select(Devices).filter(
            Devices.user_id == user_id, Devices.farm_id.is_(None)
        )
        items, next_cursor = await self.cursor_paginate(
            self.db, query, sort_column, cursor, limit
        )
        return items, next_cursor

    async def get_all_devices(
        self,
        user_id: int,
        sort_column: str,
        cursor: Optional[str] = None,
        limit: Optional[int] = 10,
    ):
        query = select(Devices).filter(Devices.user_id == user_id)

        items, next_cursor = await self.cursor_paginate(
            self.db, query, sort_column, cursor, limit
        )
        return items, next_cursor

    async def get_farms_devices(
        self,
        user_id:int,
        farm_entity: Farms,
        sort_column: str,
        cursor: Optional[str] = None,
        limit: Optional[int] = 10,
    ):
        query = select(Devices).filter(Devices.farm_id == farm_entity.farm_id, Devices.user_id == user_id)
        items, next_cursor = await self.cursor_paginate(
            self.db, query, sort_column, cursor, limit
        )
        return items, next_cursor
    

    async def assign_device_to_farm(self, device_entity, farm_entity):
        device_entity.farm_id = farm_entity.farm_id
        await self.db.commit()
        return device_entity