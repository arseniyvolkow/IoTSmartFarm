from fastapi import APIRouter, Depends, HTTPException, Query, Path, UploadFile, File
from ..database import get_db
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Annotated, Optional
import httpx
from pydantic import BaseModel
from starlette import status
from ..models import Devices, Sensors, Farms
from ..utils import login_via_token, BaseService
from sqlalchemy import select
router = APIRouter(
    prefix='/devices',
    tags=['Devices']
)


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


class DeviceSchema(BaseModel):
    unique_device_id: str
    user_id: int
    farm_id: str
    device_ip_address: str
    model_number: str
    firmware_version: str
    status: str


class CursorPagination(BaseModel):
    items: list[DeviceSchema]
    next_cursor: Optional[str] = None


class DeviceService(BaseService):
    """
    A service class for managing device-related operations.

    Methods:
        get(device_id: str):
            Retrieves a device by its unique ID.
        create(user_id: int, device_data: AddNewDevice):
            Creates a new device and its associated sensors.
    """
    async def get(self, device_id: str):
        query = select(Devices).filter(
            Devices.unique_device_id == device_id)
        result = await self.db.execute(query)
        device = result.scalar_one_or_none()
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail='Device not found')
        return device

    async def create(self, user_id, device_data: AddNewDevice):
        query = select(Devices).filter(
            Devices.unique_device_id == device_data.unique_device_id)
        result = await self.db.execute(query)
        existing_device = result.scalar_one_or_none()
        if existing_device:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Device already exists!")
        device_entity = Devices(
            unique_device_id=device_data.unique_device_id,
            user_id=user_id,
            device_ip_address=device_data.device_ip_address,
            model_number=device_data.model_number,
            firmware_version=device_data.firmware_version,
            status='inactive'
        )
        try:
            self.db.add(device_entity)
            await self.db.flush()
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
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Device with this unique ID already exists (DB constraint error)."
            )
        except Exception as e:
            await self.db.rollback()
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

            device_entity = await device_service.create(
                user_id, device_data)
            return {"status": "success", "device_id": device_entity.unique_device_id}

        except httpx.RequestError:
            return {
                'status': 'error',
                'message': 'User service unavailable!'
            }


@router.get('/unsigned-devices', status_code=status.HTTP_200_OK, response_model=CursorPagination)
async def unsigned_sensor(
        db: db_dependency,
        sort_column: str,
        cursor: Optional[str] = Query(None),
        limit: Optional[int] = Query(10, ge=10, le=200),
        token: str = Query(max_length=250)):
    user_info = await login_via_token(token)
    user_id = user_info.get('id')
    query = select(Devices).filter(
        Devices.user_id == user_id,
        Devices.farm_id.is_(None)
    )
    device_service = DeviceService(db)
    items, next_cursor = await device_service.cursor_paginate(db, query, sort_column, cursor, limit)
    return {
        'items': items,
        'next_cursor': next_cursor
    }


@router.get('/all-devices', status_code=status.HTTP_200_OK)
async def all_devices(db: db_dependency,
                      sort_column: str,
                      cursor: Optional[str] = Query(None),
                      limit: Optional[int] = Query(10, ge=10, le=200),
                      token: str = Query(max_length=250)):
    user_entity = await login_via_token(token)
    query = select(Devices).filter(
        Devices.user_id == user_entity.get('id'))
    device_service = DeviceService(db)
    items, next_cursor = await device_service.cursor_paginate(db, query, sort_column, cursor, limit)
    return {
        'items': items,
        'next_cursor': next_cursor
    }


@router.get('/all-devices/{farm_id}', status_code=status.HTTP_200_OK)
async def farm_devices(db: db_dependency,
                       sort_column: str,
                       farm_id: str = Path(max_length=100),
                       cursor: Optional[str] = Query(None),
                       limit: Optional[int] = Query(10, ge=10, le=200),
                       token: str = Query(max_length=250)):
    user_entity = await login_via_token(token)
    farm_query = select(Farms).filter(Farms.farm_id == farm_id).first()
    farm_result = await db.execute(farm_query)
    farm_entity = farm_result.scalar_one_or_none()
    if farm_entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Farm does not exist!')
    if farm_entity.user_id != user_entity.get('id'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='No access to this device!'
        )
    query = select(Devices).filter(Devices.farm_id == farm_entity.farm_id)
    device_service = DeviceService(db)
    items, next_cursor = await device_service.cursor_paginate(db, query, sort_column, cursor, limit)
    return {
        'items': items,
        'next_cursor': next_cursor
    }


@router.patch('/assign-device-to-farm', status_code=status.HTTP_200_OK)
async def assign_device(
        db: db_dependency,
        token: str = Query(max_length=250),
        device_id: str = Query(max_length=100),
        farm_id: str = Query(max_length=100)):

    farm_query = select(Farms).filter(Farms.farm_id == farm_id)
    farm_result = await db.execute(farm_query)
    farm_entity = farm_result.scalar_one_or_none()
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
    device_entity = await device_service.get(device_id)
    await device_service.check_access(device_entity, user_id)
    device_entity.farm_id = farm_entity.farm_id
    await db.commit()
    return {'details': 'Device assigned to farm!'}


@router.patch('/device/{device_id}', status_code=status.HTTP_200_OK)
async def update_device_info(db: db_dependency, token: str = Query(max_length=250), new_status: str = Query(max_length=15, regex="^(active|inactive|maintenance)$"), device_id: str = Path(max_length=250)):
    user_info = await login_via_token(token)
    user_id = user_info.get('id')
    device_service = DeviceService(db)
    device_entity = await device_service.get(device_id)
    await device_service.check_access(device_entity, user_id)
    await device_service.update(device_entity, status=new_status)
    return new_status


@router.delete('/device/{device_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(db: db_dependency, token: str = Query(max_length=250),  device_id: str = Path(max_length=250)):
    user_info = await login_via_token(token)
    user_id = user_info.get('id')
    device_service = DeviceService(db)
    device_entity = await device_service.get(device_id)
    await device_service.check_access(device_entity, user_id)
    await device_service.delete(device_entity)


@router.post('/upload_firmware/{device_id}', status_code=status.HTTP_200_OK)
async def device_firmware_update(db: db_dependency,
                                 file: UploadFile = File(...),
                                 device_id: str = Path(max_length=100),
                                 token: str = Query(max_length=250)):
    user_info = await login_via_token(token)
    user_id = user_info.get('id')
    device_service = DeviceService(db)
    device_entity = await device_service.get(device_id)
    await device_service.check_access(device_entity, user_id)
    try:
        firmware = await file.read()
        async with httpx.AsyncClient() as client:
            device_response = await client.post(url=f'http://{device_entity.device_ip_address}/update', files={'firmware': firmware})
            if device_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Firmware update failed with status code {device_response.status_code}: {device_response.text}"
                )
        return {'status': 'success', 'device_response': device_response.text}
    except Exception as e:
        return {'status': 'error', 'detail': str(e)}
