from fastapi import HTTPException
from starlette import status
from ..utils import BaseService
from ..models import CropManagment
from sqlalchemy import select
from ..schemas import CropManagmentModel


class CropService(BaseService):
    async def get(self, crop_id):
        query = select(CropManagment).filter(CropManagment.crop_id == crop_id)
        result = await self.db.execute(query)
        crop_entity = result.scalar_one_or_none()
        if not crop_entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Crop not found"
            )
        return crop_entity

    async def create(self, crop: CropManagmentModel, user_id):
        crop_data_dict = crop.model_dump()
        crop_data_dict["user_id"] = user_id
        crop_entity = CropManagment(**crop_data_dict)
        self.db.add(crop_entity)
        await self.db.commit()


    async def assign_crop_to_farm(self, farm_entity, crop_entity):
        farm_entity.farm_id = crop_entity.farm_id
        await self.db.commit()
        return farm_entity