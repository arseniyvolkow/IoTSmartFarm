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
    CropRead,
)
from ..services.crops_service import CropService
from ..dependencies import db_dependency, CurrentUserDependency

router = APIRouter(prefix="/crop", tags=["Crops"])


@router.post("/crop", status_code=status.HTTP_200_OK, response_model=CropManagmentRead)
async def add_new_crop(
    db: db_dependency,
    crop: CropManagmentCreate,
    current_user: CurrentUserDependency,
):
    crop_service = CropService(db)
    new_crop_entity = await crop_service.create(crop, current_user.id)
    return new_crop_entity


@router.get(
    "/crop/{crop_id}", status_code=status.HTTP_200_OK, response_model=CropManagmentRead
)
async def get_info_about_crop(
    db: db_dependency,
    current_user: CurrentUserDependency,
    crop_id: str = Path(max_length=100),
):
    crop_service = CropService(db)
    crop_entity = await crop_service.get(crop_id)
    await crop_service.check_access(crop_entity, current_user.id)
    return crop_entity


@router.put("/crop/{crop_id}", status_code=status.HTTP_200_OK)
async def change_crop_info(
    crop_data: CropManagmentUpdate,
    db: db_dependency,
    current_user: CurrentUserDependency,
    crop_id: str = Path(max_length=100),
):
    crop_service = CropService(db)
    crop_entity = await crop_service.get(crop_id)
    await crop_service.check_access(crop_entity, current_user.id)
    new_crop_entity = await crop_service.update(crop_entity, crop_data)
    return new_crop_entity


@router.post("/crop-type", status_code=status.HTTP_201_CREATED, response_model=CropRead)
async def new_crop_type(
    db: db_dependency,
    current_user: CurrentUserDependency,
    crop_name: str = Query(max_length=100),
) -> CropRead:
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
    return crop_type_entity


@router.get(
    "/all", status_code=status.HTTP_200_OK, response_model=CropManagmentPagination
)
async def all_crops(
    db: db_dependency,
    current_user: CurrentUserDependency,
    sort_column: Optional[str] = None,
    cursor: Optional[str] = Query(None),
    limit: Optional[int] = Query(10, ge=10, le=200),
) -> CropManagmentPagination:
    query = select(CropManagement)
    crop_service = CropService(db)
    items, next_cursor = await crop_service.cursor_paginate(
        db, query, sort_column, cursor, limit
    )
    return {"items": items, "next_cursor": next_cursor}


@router.get(
    "/all-crop-types",
    status_code=status.HTTP_200_OK,
    response_model=CropTypesPagination,
)
async def all_crop_types(
    db: db_dependency,
    sort_column: Optional[str] = None,
    cursor: Optional[str] = Query(None),
    limit: Optional[int] = Query(10, ge=10, le=200),
) -> CropTypesPagination:
    query = select(Crops)
    crop_service = CropService(db)
    items, next_cursor = await crop_service.cursor_paginate(
        db, query, sort_column, cursor, limit
    )
    return {"items": items, "next_cursor": next_cursor}
