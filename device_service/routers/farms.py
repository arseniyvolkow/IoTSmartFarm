from fastapi import APIRouter, Depends, HTTPException, Query, Path, Header
from starlette import status
from ..database import SessionLocal
from sqlalchemy.orm import Session
from typing import Annotated, Optional
from pydantic import BaseModel
from ..utils import login_via_token, BaseService
from ..models import Farms, CropManagement
from datetime import date
from .crops import CropService

router = APIRouter(
    prefix='/farms',
    tags=['Farms and Crops management']
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]


class FarmModel(BaseModel):
    farm_name: str
    total_area: int
    location: str
    crop: Optional[str] = None


class FarmService(BaseService):
    def create(self, farm: FarmModel, user_id):
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token or user not found')

        farm_entity = Farms(
            farm_name=farm.farm_name,
            total_area=farm.total_area,
            user_id=user_id,
            location=farm.location,
        )
        self.db.add(farm_entity)
        self.db.commit()

    def get(self, farm_id):
        farm_entity = self.db.query(Farms).filter_by(farm_id=farm_id).first()
        if not farm_entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail='Farm not found')
        return farm_entity


@router.post('/farm', status_code=status.HTTP_201_CREATED)
async def add_new_farm(db: db_dependency, farm: FarmModel, token: str = Header(max_length=250)):
    user_entity = await login_via_token(token)
    user_id = user_entity.get('id')
    farm_service = FarmService(db)
    farm_service.create(farm, user_id)
    return {'message': 'Farm added successfully'}


async def get_all_farms(db: db_dependency, token: str = Header(max_length=250)):
    user_entity = await login_via_token(token)
    if not user_entity or 'id' not in user_entity:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token or user not found')
    all_farms = db.query(Farms).filter(
        Farms.user_id == user_entity.get('id')).all()
    return all_farms


@router.get('/farm/{farm_id}')
async def get(db: db_dependency, token: str = Header(max_length=250), farm_id: str = Path(max_length=100)):
    user_entity = await login_via_token(token)
    user_id = user_entity.get('id')
    farm_service = FarmService(db)
    farm_entity = farm_service.get(farm_id)
    farm_service.check_access(farm_entity, user_id)
    return farm_entity


@router.put('/farm/{farm_id}')
async def update_farm_info(db: db_dependency, farm: FarmModel, token: str = Header(max_length=250), farm_id: str = Path(max_length=100)):
    user_entity = await login_via_token(token)
    farm_service = FarmService(db)
    user_entity = await login_via_token(token)
    farm_entity = farm_service.get(farm_id)
    farm_service.update(farm_entity, farm)
    return {'details': f'Farm {farm_entity.farm_id} info was updated!'}


@router.patch('/farm/{farm_id}', status_code=status.HTTP_200_OK)
async def assing_crop_to_farm(db: db_dependency, farm_id: str = Path(max_length=100), crop_id: str = Query(max_length=100), token: str = Header(max_length=250)):
    farm_service = FarmService(db)
    farm_entity = farm_service.get(farm_id)
    user_entity = await login_via_token(token)
    user_id = user_entity.get('id')
    farm_service.check_access(farm_entity, user_id)
    crop_service = CropService(db)
    crop_entity = crop_service.get(crop_id)
    farm_entity.crop_id = crop_entity.crop_id
    db.commit()
    return {'details': 'Crop assigned to farm!'}


@router.delete('/farm/{farm_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_farm(db: db_dependency, farm_id: str = Path(max_length=100), token: str = Header(max_length=250)):
    user_entity = await login_via_token(token)
    user_id = user_entity.get('id')
    farm_service = FarmService(db)
    farm_entity = farm_service.get(farm_id)
    farm_service.check_access(farm_entity, user_id)
    farm_service.delete(farm_entity)
    return {'details': f'Farm {farm_entity.farm_id} was deleted'}
