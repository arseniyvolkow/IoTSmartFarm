from farm_management_service.repositories.base_repository import BaseRepository
from farm_management_service.models import CropManagement
from sqlalchemy import select
from typing import Optional

class CropRepository(BaseRepository):
    async def get_by_id(self, crop_id: str) -> Optional[CropManagement]:
        query = select(CropManagement).filter(CropManagement.crop_id == crop_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create(self, crop_entity: CropManagement) -> CropManagement:
        self.db.add(crop_entity)
        await self.db.commit()
        await self.db.refresh(crop_entity)
        return crop_entity
