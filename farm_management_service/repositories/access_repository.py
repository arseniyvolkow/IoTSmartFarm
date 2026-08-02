from farm_management_service.repositories.base_repository import BaseRepository
from farm_management_service.models import FarmAccess, Farms
from sqlalchemy import select, delete
from typing import List, Optional
from farm_management_service.enums import AccessLevel

class AccessRepository(BaseRepository):
    async def get_farm_owner(self, farm_id: str) -> Optional[str]:
        query = select(Farms.user_id).filter(Farms.farm_id == farm_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_access_entry(self, farm_id: str, user_id: str) -> Optional[FarmAccess]:
        query = select(FarmAccess).filter(
            FarmAccess.farm_id == farm_id,
            FarmAccess.user_id == user_id
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_access(self, farm_id: str, user_id: str, access_level: AccessLevel) -> FarmAccess:
        new_access = FarmAccess(
            farm_id=farm_id,
            user_id=user_id,
            access_level=access_level
        )
        self.db.add(new_access)
        await self.db.commit()
        await self.db.refresh(new_access)
        return new_access

    async def update_access(self, access_entry: FarmAccess, access_level: AccessLevel) -> FarmAccess:
        access_entry.access_level = access_level
        await self.db.commit()
        await self.db.refresh(access_entry)
        return access_entry

    async def delete_access(self, farm_id: str, user_id: str) -> int:
        query = delete(FarmAccess).filter(
            FarmAccess.farm_id == farm_id,
            FarmAccess.user_id == user_id
        )
        result = await self.db.execute(query)
        await self.db.commit()
        return result.rowcount

    async def get_all_access_for_farm(self, farm_id: str) -> List[FarmAccess]:
        query = select(FarmAccess).filter(FarmAccess.farm_id == farm_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())
