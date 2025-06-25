from fastapi import APIRouter, Depends, HTTPException, Query, Path
from starlette import status
from ..database import get_db
from sqlalchemy.orm import Session
from typing import Annotated, Optional
from pydantic import BaseModel
from ..utils import BaseService, get_current_user
from ..models import Farms
from .crops import CropService
from sqlalchemy import select

router = APIRouter(prefix="/farms", tags=["Farms and Crops management"])


db_dependency = Annotated[Session, Depends(get_db)]


class FarmModel(BaseModel):
    """
    Represents the data model for a farm, including its name, total area, location,
    and an optional crop. Used for validating and transferring farm-related data.
    """

    farm_name: str
    total_area: int
    location: str
    crop: Optional[str] = None


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


@router.post("/farm", status_code=status.HTTP_201_CREATED)
async def add_new_farm(
    db: db_dependency,
    current_user: Annotated[dict, Depends(get_current_user)],
    farm: FarmModel,
):
    farm_service = FarmService(db)
    await farm_service.create(farm, current_user["id"])
    return {"message": "Farm added successfully"}


async def get_all_farms(
    db: db_dependency,
    current_user: Annotated[dict, Depends(get_current_user)],
    sort_column: str,
    cursor: Optional[str] = Query(None),
    limit: Optional[int] = Query(10, le=200),
):
    query = select(Farms).filter(Farms.user_id == current_user["id"])
    farm_service = FarmService(db)
    items, next_cursor = await farm_service.cursor_paginate(
        db, query, sort_column, cursor, limit
    )
    return {"items": items, "next_cursor": next_cursor}


@router.get("/farm/{farm_id}")
async def get(
    db: db_dependency,
    current_user: Annotated[dict, Depends(get_current_user)],
    farm_id: str = Path(max_length=100),
):
    farm_service = FarmService(db)
    farm_entity = await farm_service.get(farm_id)
    await farm_service.check_access(farm_entity, current_user["id"])
    return farm_entity


@router.put("/farm/{farm_id}")
async def update_farm_info(
    db: db_dependency,
    farm: FarmModel,
    current_user: Annotated[dict, Depends(get_current_user)],
    farm_id: str = Path(max_length=100),
):
    farm_service = FarmService(db)
    farm_entity = await farm_service.get(farm_id)
    farm_service.check_access(farm_entity, current_user["id"])
    await farm_service.update(farm_entity, **farm.model_dump())
    return {"details": f"Farm {farm_entity.farm_id} info was updated!"}


@router.patch("/farm/{farm_id}", status_code=status.HTTP_200_OK)
async def assign_crop_to_farm(
    db: db_dependency,
    current_user: Annotated[dict, Depends(get_current_user)],
    farm_id: str = Path(max_length=100),
    crop_id: str = Query(max_length=100),
):
    farm_service = FarmService(db)
    farm_entity = await farm_service.get(farm_id)
    await farm_service.check_access(farm_entity, current_user["id"])
    crop_service = CropService(db)
    crop_entity = await crop_service.get(crop_id)
    farm_entity.crop_id = crop_entity.crop_id
    await db.commit()
    return {"details": "Crop assigned to farm!"}


@router.delete("/farm/{farm_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_farm(
    db: db_dependency,
    current_user: Annotated[dict, Depends(get_current_user)],
    farm_id: str = Path(max_length=100),
):
    farm_service = FarmService(db)
    farm_entity = await farm_service.get(farm_id)
    await farm_service.check_access(farm_entity, current_user["id"])
    await farm_service.delete(farm_entity)
    return {"details": f"Farm {farm_entity.farm_id} was deleted"}
