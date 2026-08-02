from farm_management_service.repositories.base_repository import BaseRepository
from farm_management_service.models import Devices, FarmAccess
from farm_management_service.schemas import DeviceCreate
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import select, or_
from typing import Optional

class DeviceRepository(BaseRepository):
    async def get_by_id(self, device_id: str) -> Optional[Devices]:
        query = select(Devices).filter(Devices.device_id == device_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_unique_id(self, unique_device_id: str) -> Optional[Devices]:
        query = select(Devices).filter(Devices.unique_device_id == unique_device_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_and_flush(self, device_data: DeviceCreate) -> Devices:
        device_entity = Devices(
            unique_device_id=device_data.unique_device_id,
            device_ip_address=device_data.device_ip_address,
            model_number=device_data.model_number,
            firmware_version=device_data.firmware_version,
        )
        self.db.add(device_entity)
        await self.db.flush()
        return device_entity

    async def get_device_id_by_unique_id(self, unique_device_id: str) -> str:
        query_device = select(Devices.device_id).filter(
            Devices.unique_device_id == unique_device_id
        )
        result = await self.db.execute(query_device)
        return str(result.scalar_one())

    async def commit(self):
        await self.db.commit()

    async def rollback(self):
        await self.db.rollback()

    async def refresh(self, entity):
        await self.db.refresh(entity)

    async def get_unassigned_to_user_devices(self, sort_column: str, cursor: Optional[str] = None, limit: int = 10):
        query = (
            select(Devices)
            .filter(Devices.user_id.is_(None))
            .options(joinedload(Devices.sensors), joinedload(Devices.actuators))
        )
        return await self.cursor_paginate(self.db, query, sort_column, cursor, limit)

    async def get_unassigned_to_farm_devices(self, user_id: str, sort_column: str, cursor: Optional[str] = None, limit: int = 10):
        query = (
            select(Devices)
            .filter(Devices.user_id == user_id, Devices.farm_id.is_(None))
            .options(joinedload(Devices.sensors), joinedload(Devices.actuators))
        )
        return await self.cursor_paginate(self.db, query, sort_column, cursor, limit)

    async def get_user_devices(self, user_id: str, sort_column: str, farm_id: Optional[str] = None, cursor: Optional[str] = None, limit: int = 10):
        query = select(Devices).options(
            selectinload(Devices.sensors), selectinload(Devices.actuators)
        )
        
        if farm_id:
            query = query.filter(Devices.farm_id == farm_id)
            query = query.outerjoin(FarmAccess, Devices.farm_id == FarmAccess.farm_id)
            query = query.filter(
                or_(
                    Devices.user_id == user_id,
                    FarmAccess.user_id == user_id
                )
            )
        else:
            query = query.outerjoin(FarmAccess, Devices.farm_id == FarmAccess.farm_id)
            query = query.filter(
                or_(
                    Devices.user_id == user_id,
                    FarmAccess.user_id == user_id
                )
            )

        return await self.cursor_paginate(self.db, query.distinct(), sort_column, cursor, limit)
