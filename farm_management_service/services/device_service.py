from fastapi import HTTPException, Depends
from sqlalchemy.exc import IntegrityError
from starlette import status
from ..models import Devices
from ..base_service import BaseService
from sqlalchemy import select
from ..schemas import DeviceCreate, DeviceRead, DevicePagination
from sqlalchemy.orm import joinedload, selectinload
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..services.sensor_service import SensorService
from ..services.actuators_service import ActuatorService


class DeviceService(BaseService):
    def __init__(
        self,
        db: AsyncSession = Depends(get_db),
    ):
        super().__init__(db)
        # Instantiate other services, passing the SAME database session
        self.sensor_service = SensorService(db)
        self.actuator_service = ActuatorService(db)

    async def get(self, device_id: str) -> Devices:
        query = select(Devices).filter(Devices.device_id == device_id)
        result = await self.db.execute(query)
        device = result.scalar_one_or_none()
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
            )
        return device

    async def create(self, device_data: DeviceCreate) -> DeviceRead:
        # 1. Check if device already exists (without raising exception)
        query = select(Devices).filter(
            Devices.unique_device_id == device_data.unique_device_id
        )
        result = await self.db.execute(query)
        existing_device = result.scalar_one_or_none()

        if existing_device:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Device already exists!"
            )

        # 2. Create the main device object and add it to the session
        device_entity = Devices(
            unique_device_id=device_data.unique_device_id,
            device_ip_address=device_data.device_ip_address,
            model_number=device_data.model_number,
            firmware_version=device_data.firmware_version,
        )
        self.db.add(device_entity)
        await self.db.flush()  # This generates the device_id

        # Get the device_id from the flushed entity using direct attribute access
        try:
            device_id = str(device_entity.__dict__["device_id"])
        except KeyError:
            # Fallback: query the database to get the device_id
            query_device = select(Devices.device_id).filter(
                Devices.unique_device_id == device_data.unique_device_id
            )
            result = await self.db.execute(query_device)
            device_id = result.scalar_one()

        # 3. Use the dedicated services to stage sensors and actuators
        self.sensor_service.add_sensors_to_session(
            device_id=device_id,
            sensors_list=device_data.sensors_list,
        )
        self.actuator_service.add_actuators_to_session(
            device_id=device_id,
            actuators_list=device_data.actuators_list,
        )

        # 4. Commit everything in a single atomic transaction
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A database integrity error occurred. The device ID might already exist.",
            )
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred: {str(e)}",
            )
        await self.db.refresh(device_entity)
        return device_entity

    async def get_unassigned_to_user_devices(
        self,
        sort_column: str,
        cursor: Optional[str] = None,
        limit: Optional[int] = 10,
    ):
        query = (
            select(Devices)
            .filter(Devices.user_id.is_(None))
            .options(joinedload(Devices.sensors), joinedload(Devices.actuators))
        )
        items, next_cursor = await self.cursor_paginate(
            self.db, query, sort_column, cursor, limit
        )
        return items, next_cursor

    async def get_unassigned_to_farm_devices(
        self,
        user_id: str,
        sort_column: str,
        cursor: Optional[str] = None,
        limit: Optional[int] = 10,
    ):
        query = (
            select(Devices)
            .filter(Devices.user_id == user_id, Devices.farm_id.is_(None))
            .options(joinedload(Devices.sensors), joinedload(Devices.actuators))
        )
        items, next_cursor = await self.cursor_paginate(
            self.db, query, sort_column, cursor, limit
        )
        return items, next_cursor

    async def get_user_devices(
        self,
        user_id: str,
        sort_column: str,
        farm_id: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = 10,
    ) -> DevicePagination:
        query = select(Devices).filter(Devices.user_id == user_id)

        if farm_id:
            query = query.filter(Devices.farm_id == farm_id)
            # TODO: The FastAPI router must ensure the user has access to this farm_id
            # before calling this service method.
        query = query.options(
            selectinload(Devices.sensors), selectinload(Devices.actuators)
        )
        # 3. Perform cursor pagination
        items, next_cursor = await self.cursor_paginate(
            self.db, query, sort_column, cursor, limit
        )
        return items, next_cursor
