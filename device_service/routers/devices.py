from fastapi import APIRouter, Depends, HTTPException, Query, Path, UploadFile, File
from ..database import SessionLocal
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Annotated, Optional
import httpx
from pydantic import BaseModel
from starlette import status
from ..models import Devices, Sensors, Farms
from datetime import datetime, timezone
from ..utils import login_via_token, BaseService


router = APIRouter(
    prefix='/devices',
    tags=['Devices']
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]


class SensorInfo(BaseModel):
    sensor_type: str
    units_of_measure: str
    max_value: float
    min_value: float


class AddNewDevice(BaseModel):
    username: str
    password: str
    unique_device_id: str
    device_ip_address: str
    model_number: str
    firmware_version: str
    sensors_list: list[SensorInfo]


class UpdateDeviceInfo(BaseModel):
    status: str


class DeviceService(BaseService):
    def get(self, device_id: str):
        device = self.db.query(Devices).filter_by(
            unique_device_id=device_id).first()
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail='Device not found')
        return device

    def create(self, user_id, device_data: AddNewDevice):
        existing_device = self.db.query(Devices).filter_by(
            unique_device_id=device_data.unique_device_id).first()
        if existing_device:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Device already exists!")

        device_entity = Devices(
            unique_device_id=device_data.unique_device_id,
            user_id=user_id,
            device_ip_address=device_data.device_ip_address,
            installation_date=datetime.now(timezone.utc),
            model_number=device_data.model_number,
            firmware_version=device_data.firmware_version,
            status='inactive'
        )
        try:
            self.db.add(device_entity)
            sensor_entities = [
                Sensors(
                    device_id=device_entity.unique_device_id,
                    sensor_type=sensor.sensor_type,
                    units_of_measure=sensor.units_of_measure,
                    max_value=sensor.max_value,
                    min_value=sensor.min_value,
                )
                for sensor in device_data.sensors_list
            ]

            self.db.bulk_save_objects(sensor_entities)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Device with this unique ID already exists (DB constraint error)."
            )
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error: {str(e)}"
            )
        return device_entity



@router.post('/device', status_code=status.HTTP_201_CREATED,)
async def new_device(db: db_dependency, device_data: AddNewDevice):
    async with httpx.AsyncClient() as client:
        try:
            user_service_response = await client.post(
                "http://user_service:8005/auth/login_for_id",
                data={
                    "username": device_data.username,
                    "password": device_data.password
                }
            )
            if user_service_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail='Incorrect login data')

            user_info = user_service_response.json()
            user_id = user_info.get('user_id')

            device_service = DeviceService(db)

            device_entity = device_service.create_new_device(
                user_id, device_data)
            return {"status": "success", "device_id": device_entity.unique_device_id}

        except httpx.RequestError:
            return {
                'status': 'error',
                'message': 'User service unavailable!'
            }


@router.get('/unsigned-devices', status_code=status.HTTP_200_OK)
async def unsigned_sensor(db: db_dependency, token: str = Query(max_length=250)):

    user_info = await login_via_token(token)
    user_id = user_info.get('id')
    uassigned_devices = db.query(Devices).filter(
        Devices.user_id == user_id).filter(Devices.farm_id.is_(None)).all()
    return uassigned_devices


@router.get('/all-devices', status_code=status.HTTP_200_OK)
async def all_devices(db: db_dependency, token: str = Query(max_length=250)):
    user_entity = await login_via_token(token)
    all_device = db.query(Devices).filter_by(
        user_id=user_entity.get('id')).all()
    return all_device


@router.get('/all-devices/{farm_id}', status_code=status.HTTP_200_OK)
async def farm_devices(db: db_dependency,  farm_id: str = Path(max_length=100), token: str = Query(max_length=250)):
    user_entity = await login_via_token(token)
    farm_entity = db.query(Farms).filter_by(farm_id=farm_id).first()
    if farm_entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Farm does not exist!')
    if farm_entity.user_id != user_entity.get('id'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='No access to this device!'
        )
    farm_devices = db.query(Devices).filter_by(farm_id=farm_entity.farm_id)
    return farm_devices


@router.patch('/assign-device-to-farm', status_code=status.HTTP_200_OK)
async def assign_device(
        db: db_dependency,
        token: str = Query(max_length=250),
        device_id: str = Query(max_length=100),
        farm: str = Query(max_length=100)):
    farm_entity = db.query(Farms).filter_by(farm_id=farm).first()
    if farm_entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Farm does not exist!')
    user_info = await login_via_token(token)
    user_id = user_info.get('id')
    if farm_entity.user_id != user_info.get('id'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='No access to this farm!'
        )
    device_service = DeviceService(db)
    device_entity = device_service.get(device_id)
    device_service.check_access(device_entity, user_id)
    device_entity.farm_id = farm_entity.farm_id
    db.commit()
    return {'details': 'Device assigned to farm!'}


@router.patch('/device/{device_id}', status_code=status.HTTP_200_OK)
async def update_device_info(db: db_dependency, token: str = Query(max_length=250), new_status: str = Query(max_length=15), device_id: str = Path(max_length=250)):
    user_info = await login_via_token(token)
    user_id = user_info.get('id')
    device_service = DeviceService(db)
    device_entity = device_service.get(device_id)
    device_service.check_access(device_entity, user_id)
    device_service.update(device_entity, new_status)


@router.delete('/device/{device_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(db: db_dependency, token: str = Query(max_length=250),  device_id: str = Path(max_length=250)):
    user_info = await login_via_token(token)
    user_id = user_info.get('id')
    device_service = DeviceService(db)
    device_entity = device_service.get(device_id)
    device_service.check_access(device_entity, user_id)
    device_service.delete(device_entity)


@router.post('/upload_firmware/{device_id}', status_code=status.HTTP_200_OK)
async def device_firmware_update(db: db_dependency,
                                 file: UploadFile = File(...),
                                 device_id: str = Path(max_length=100),
                                 token: str = Query(max_length=250)):
    user_info = await login_via_token(token)
    user_id = user_info.get('id')
    device_service = DeviceService(db)
    device_entity = device_service.get(device_id)
    device_service.check_access(device_entity, user_id)
    try:
        firmware = await file.read()
        async with httpx.AsyncClient() as client:
            device_response = await client.post(url=f'http://{device_entity.device_ip_address}/update', files={'firmware': firmware})
        return {'status': 'success', 'device_response': device_response.text}
    except Exception as e:
        return {'status': 'error', 'detail': str(e)}
