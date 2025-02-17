from fastapi import APIRouter, Depends, HTTPException, Query, Path, Header
from starlette import status
from ..database import SessionLocal
from sqlalchemy.orm import Session
from typing import Annotated, Optional
from pydantic import BaseModel
from ..utils import login_via_token
from ..models import Farms, CropManagement
from datetime import date

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


@router.post('/farm', status_code=status.HTTP_201_CREATED)
async def add_new_farm(db: db_dependency, farm_request: FarmModel, token: str = Header(max_length=250)):
    user_entity = await login_via_token(token)
    if user_entity is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token or user not found')
    farm_entity = Farms(
        farm_name=farm_request.farm_name,
        total_area=farm_request.total_area,
        owner_id=user_entity.get('id'),
        location=farm_request.location,
    )
    db.add(farm_entity)
    db.commit()
    return {'details': 'New farm created!'}
async def get_all_farms(db: db_dependency, token: str = Header(max_length=250)):
    user_entity = await login_via_token(token)
    if not user_entity or 'id' not in user_entity:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token or user not found')
    all_farms = db.query(Farms).filter(
        Farms.owner_id == user_entity.get('id')).all()
    return all_farms

@router.get('/farm/{farm_id}')
async def get_farm_by_id(db: db_dependency, token: str = Header(max_length=250), farm_id: str = Path(max_length=100)):
    user_entity = await login_via_token(token)
    print("User entity:", user_entity)  
    farm_entity = db.query(Farms).filter_by(farm_id=farm_id).first()
    print("Farm owner_id:", farm_entity.owner_id, type(farm_entity.owner_id))
    print("User entity id:", user_entity.get('id'), type(user_entity.get('id')))
    if farm_entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Farm does not exist!')
    if farm_entity.owner_id != str(user_entity.get('id')):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail='No access!')
    return farm_entity


@router.put('/farm/{farm_id}')
async def update_farm_info(db: db_dependency, farm_request: FarmModel, token: str = Header(max_length=250), farm_id: str = Path(max_length=100)):
    user_entity = await login_via_token(token)
    farm_entity = db.query(Farms).filter_by(farm_id=farm_id).first()
    if farm_entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Farm does not exist!')
    if farm_entity.owner_id != user_entity.get('id'):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail='No access!')
    farm_entity.farm_name = farm_request.farm_name
    farm_entity.total_area = farm_request.total_area
    farm_entity.location = farm_request.location
    db.add(farm_entity)
    db.commit()
    return {'details': f'Farm {farm_entity.farm_id} info was updated!'}


@router.patch('/farm/{farm_id}', status_code=status.HTTP_200_OK)
async def assing_crop_to_farm(db: db_dependency, farm_id: str = Path(max_length=100), token: str = Header(max_length=250), crop_id: str = Query(max_length=100)):
    farm_entity = db.query(Farms).filter_by(farm_id=farm_id).first()
    if farm_entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Farm does not exist!')
    crop_entity = db.query(CropManagement).filter_by(crop_id=crop_id).first()
    user_entity = await login_via_token(token)
    if crop_entity.owner_id != user_entity.get('id') or crop_entity.owner_id != farm_entity.owner_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail='No access!')
    farm_entity.crop = crop_entity.crop_id
    db.commit()
    return {'details': 'Crop assigned to farm!'}


@router.delete('/farm/{farm_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_farm(db: db_dependency, farm_id: str = Path(max_length=100), token: str = Header(max_length=250)):
    user_entity = await login_via_token(token)
    farm_entity = db.query(Farms).filter_by(farm_id=farm_id).first()
    if farm_entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Farm does not exist!')
    if farm_entity.owner_id != user_entity.get('id'):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail='No access!')
    db.delete(farm_entity)
    db.commit()
    return {'details': f'Farm {farm_entity.farm_id} was deleted'}



class FarmService:
    def __init__(self, db: Session):
        self.db = db


    def new_farm(self, farm: FarmModel):
        pass

    
    def get_farm(self, farm_id):
        farm_entity = self.db.query(Farms).filter_by(farm_id=farm_id).first()
        if not farm_entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail='Farm not found')
        return farm_entity
    
    def check_access(self, farm: Farms, user_id):
        if farm.owner_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail='No access to this farm!')
        
    def delete_farm(self, farm: Farms, user_id):
        pass

    def update_farm(self, farm: Farms, user_id):
        pass

