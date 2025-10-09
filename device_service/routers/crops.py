from fastapi import APIRouter, HTTPException, Query, Path, status
from typing import Optional
from ..models import Crops, CropManagement
from sqlalchemy import select
from ..schemas import (
    CropManagmentCreate,
    CropManagmentUpdate,
    CropManagmentRead,
    CropManagmentPagination,
    CropTypesPagination,
)
from ..services.crops_service import CropService
from ..utils import db_dependency, user_dependency

router = APIRouter(prefix="/crop", tags=["Crops"])


@router.post("/crop", status_code=status.HTTP_200_OK)
async def add_new_crop(
    db: db_dependency,
    crop: CropManagmentCreate,
    current_user: user_dependency,
):
    crop_service = CropService(db)
    await crop_service.create(crop, current_user["id"])
    return {"message": "Crop added successfully"}


@router.get(
    "/crop/{crop_id}", status_code=status.HTTP_200_OK, response_model=CropManagmentRead
)
async def get_info_about_crop(
    db: db_dependency,
    current_user: user_dependency,
    crop_id: str = Path(max_length=100),
):
    crop_service = CropService(db)
    crop_entity = await crop_service.get(crop_id)
    await crop_service.check_access(crop_entity, current_user["id"])
    return crop_entity


@router.put("/crop/{crop_id}", status_code=status.HTTP_200_OK)
async def change_crop_info(
    crop_data: CropManagmentUpdate,
    db: db_dependency,
    current_user: user_dependency,
    crop_id: str = Path(max_length=100),
):
    crop_service = CropService(db)
    crop_entity = await crop_service.get(crop_id)
    await crop_service.check_access(crop_entity, current_user["id"])
    await crop_service.update(crop_entity, crop_data)
    return {"detail": f"Crop {crop_entity.crop_id} info was updated!"}


@router.post("/crop-type", status_code=status.HTTP_201_CREATED)
async def new_crop_type(
    db: db_dependency,
    current_user: user_dependency,
    crop_name: str = Query(max_length=100),
):
    query = select(Crops).filter(Crops.crop_name == crop_name)
    result = await db.execute(query)
    existing_crop_type = result.scalars().first()
    if existing_crop_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Crop type already exists!"
        )
    crop_type_entity = Crops(crop_name=crop_name)
    db.add(crop_type_entity)
    await db.commit()
    return {"details": f'New crop type "{crop_name}" added successfully!'}


@router.get(
    "/all", status_code=status.HTTP_200_OK, response_model=CropManagmentPagination
)
async def all_crops(
    db: db_dependency,
    current_user: user_dependency,
    sort_column: Optional[str] = None,
    cursor: Optional[str] = Query(None),
    limit: Optional[int] = Query(10, ge=10, le=200),
):
    query = select(CropManagement)
    crop_service = CropService(db)
    items, next_cursor = await crop_service.cursor_paginate(
        db, query, sort_column, cursor, limit
    )
    return {"items": items, "next_cursor": next_cursor}


@router.get(
    "/all-crop-types", status_code=status.HTTP_200_OK, response_model=CropTypesPagination
)
async def all_crop_types(
    db: db_dependency,
    sort_column: Optional[str] = None,
    cursor: Optional[str] = Query(None),
    limit: Optional[int] = Query(10, ge=10, le=200),
):
    query = select(Crops)
    crop_service = CropService(db)
    items, next_cursor = await crop_service.cursor_paginate(
        db, query, sort_column, cursor, limit
    )
    return {"items": items, "next_cursor": next_cursor}
