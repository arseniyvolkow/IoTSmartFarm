from fastapi import HTTPException
from starlette import status
from ..utils import BaseService
from ..models import Farms
from ..schemas import FarmModel
from sqlalchemy import select


class FarmService(BaseService):
    async def create(self, farm: FarmModel, user_id):
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token or user not found",
            )

        farm_entity = Farms(
            farm_name=farm.farm_name,
            total_area=farm.total_area,
            user_id=user_id,
            location=farm.location,
        )
        self.db.add(farm_entity)
        await self.db.commit()

    async def get(self, farm_id):
        query = select(Farms).filter(Farms.farm_id == farm_id)
        result = await self.db.execute(query)
        farm_entity = result.scalar_one_or_none()
        if not farm_entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found"
            )
        return farm_entity
