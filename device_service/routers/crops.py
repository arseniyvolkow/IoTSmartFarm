from fastapi import APIRouter, HTTPException, Depends, Query, Path
from starlette import status
from ..database import get_db
from sqlalchemy.orm import Session
from typing import Annotated, Optional
from pydantic import BaseModel
from ..utils import login_via_token, BaseService
from datetime import date
from ..models import Farms, CropManagment, Crops
from sqlalchemy import select
router = APIRouter(
    prefix='/crop',
    tags=['Crops']
)


db_dependency = Annotated[Session, Depends(get_db)]


class CropManagementModel(BaseModel):
    planting_date: date
    expected_harvest_date: date
    current_grow_stage: str
    crop_type_id: str


class CropService(BaseService):

    async def get(self, crop_id):
        query = select(CropManagement).filter(
            CropManagement.crop_id == crop_id)
        result = await self.db.execute(query)
        crop_entity = result.scalar_one_or_none()
        if not crop_entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail='Crop not found')
        return crop_entity

    async def create(self, crop: CropManagementModel, user_id):
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail='Invalid token or user not found')
        crop_data_dict = crop.model_dump()
        crop_data_dict['user_id'] = user_id
        crop_entity = CropManagement(**crop_data_dict)
        self.db.add(crop_entity)
        await self.db.commit()


@router.post('/crop', status_code=status.HTTP_200_OK)
async def add_new_crop(db: db_dependency, crop: CropManagementModel, token: str = Query(max_length=250)):
    user_entity = await login_via_token(token)
    user_id = user_entity.get('id')
    crop_service = CropService(db)
    await crop_service.create(crop, user_id)
    return {"message": "Crop added successfully"}


@router.get('/crop/{crop_id}', status_code=status.HTTP_200_OK)
async def get_info_about_crop(db: db_dependency, crop_id: str = Path(max_length=100), token: str = Query(max_length=250)):
    crop_service = CropService(db)
    crop_entity = await crop_service.get(crop_id)
    user_entity = await login_via_token(token)
    user_id = user_entity.get('id')
    await crop_service.check_access(crop_entity, user_id)
    return crop_entity


@router.put('/crop/{crop_id}', status_code=status.HTTP_200_OK)
async def change_crop_info(
        crop_data: CropManagementModel,
        db: db_dependency,
        token: str = Query(max_length=250),
        crop_id: str = Path(max_length=100)):
    user_entity = await login_via_token(token)
    user_id = user_entity.get('id')
    crop_service = CropService(db)
    crop_entity = await crop_service.get(crop_id)
    await crop_service.check_access(crop_entity, user_id)
    await crop_service.update(crop_entity, crop_data)
    return {'detail': f'Crop {crop_entity.crop_id} info was updated!'}


@router.post('/type', status_code=status.HTTP_201_CREATED)
async def new_crop_type(db: db_dependency, token: str = Query(max_length=250), crop_name: str = Query(max_length=100)):
    user_entity = await login_via_token(token)
    query = select(Crops).filter(Crops.crop_name == crop_name)
    result = await db.execute(query)
    existing_crop_type = result.scalars().first()
    if existing_crop_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail='Crop type already exists!'
        )
    crop_type_entity = Crops(crop_name=crop_name)
    db.add(crop_type_entity)
    await db.commit()
    return {'details': f'New crop type "{crop_name}" added successfully!'}


@router.get('/type', status_code=status.HTTP_200_OK)
async def all_crop_types(db: db_dependency,
                         sort_column: str,
                         cursor: Optional[str] = Query(None),
                         limit: Optional[int] = Query(10, ge=10, le=200)):
    query = select(Crops)
    crop_service = CropService(db)
    items, next_cursor = await crop_service.cursor_paginate(db, query, sort_column, cursor, limit)
    return {'items': items,
            'next_cursor': next_cursor}
