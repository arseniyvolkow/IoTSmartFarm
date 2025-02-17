from fastapi import APIRouter, HTTPException, Depends, Query, Path
from starlette import status
from ..database import SessionLocal
from sqlalchemy.orm import Session
from typing import Annotated, Optional
from pydantic import BaseModel
from ..utils import login_via_token
from datetime import date
from ..models import Farms, CropManagement, Crops


router = APIRouter(
    prefix='/crop',
    tags=['Crops']
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]


class CropModel(BaseModel):
    farm_id: str
    planting_date: date
    expected_harvest_date: date
    current_grow_stage: str
    crop_type_id: str


@router.post('/crop', status_code=status.HTTP_200_OK)
async def add_new_crop(db: db_dependency, crop: CropModel, token: str = Query(max_length=250)):
    farm_entity = db.query(Farms).filter_by(farm_id=crop.farm_id).first()
    if farm_entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Farm does not exist!')
    user_entity = await login_via_token(token)
    if  farm_entity.user_id != user_entity.get('id'):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail='No access!')
    crop_entity = CropManagement(**crop.model_dump(), user_id = user_entity.get('id')
    )
    db.add(crop_entity)
    db.commit()


@router.get('/сrop/{crop_id}', status_code=status.HTTP_200_OK)
async def get_info_about_crop(db: db_dependency, crop_id: str = Path(max_length=100), token: str = Query(max_length=250)):
    crop_info = db.query(CropManagement).filter_by(crop_id=crop_id).first()
    if crop_info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Crop does not exist!')
    user_entity = await login_via_token(token)
    if crop_info.user_id != user_entity.get('id'):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail='No access!')
    return crop_info


@router.put('/crop/{crop_id}', status_code=status.HTTP_200_OK)
async def change_crop_info(
        crop_data: CropModel,
        db: db_dependency, 
        token: str = Query(max_length=250),
        crop_id: str = Path(max_length=100)):
    user_entity = await login_via_token(token)
    crop_entity = db.query(CropManagement).filter_by(crop_id=crop_id).first()
    if crop_entity.owner_id != user_entity.get('id'):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail='No access!')
    crop_entity.planting_date = crop_data.planting_date
    crop_entity.farm_id = crop_data.farm_id
    crop_entity.expected_harvest_date = crop_data.expected_harvest_date
    crop_entity.current_grow_stage = crop_data.current_grow_stage
    crop_entity.crop_type_id = crop_data.crop_type_id
    db.add(crop_entity)
    db.commit()
    return {'detail': f'Crop {crop_entity.crop_id} info was updated!'}


@router.post('/type',status_code=status.HTTP_201_CREATED)
async def new_crop_type(db:db_dependency, token: str = Query(max_length=250), crop_name:str = Query(max_length=100)):
    existing_crop_type = db.query(Crops).filter_by(crop_name=crop_name).first()
    if existing_crop_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail='Crop type already exists!'
        )
    user_entity = await login_via_token(token)
    crop_type_entity = Crops(crop_name = crop_name)
    db.add(crop_type_entity)
    db.commit()
    return {'details': f'New crop type "{crop_name}" added successfully!'}

@router.get('/type', status_code=status.HTTP_200_OK)
async def all_crop_types(db:db_dependency):
    crop_type_entitys = db.query(Crops).all()
    return crop_type_entitys

