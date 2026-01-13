from common.schemas import CurrentUser
from common.security import get_current_user_identity
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from farm_management_service.database import get_db
from farm_management_service.services.actuators_service import ActuatorService
from farm_management_service.services.crops_service import CropService
from farm_management_service.services.device_service import DeviceService
from farm_management_service.services.farm_service import FarmService
from farm_management_service.services.sensor_service import SensorService

db_dependency = Annotated[AsyncSession, Depends(get_db)]

async def get_actuator_service(db: db_dependency) -> ActuatorService:
    return ActuatorService(db)


async def get_crop_service(db: db_dependency) -> CropService:
    return CropService(db)


async def get_device_service(db: db_dependency) -> DeviceService:
    return DeviceService(db)

async def get_farm_service(db: db_dependency) -> FarmService:
    return FarmService(db)


async def get_sensor_service(db: db_dependency) -> SensorService:
    return SensorService(db)




CurrentUserDependency = Annotated[CurrentUser, Depends(get_current_user_identity)]

DeviceServiceDependency = Annotated[DeviceService, Depends(get_device_service)]

CropServiceDependency = Annotated[CropService, Depends(get_crop_service)]

FarmServiceDependency = Annotated[FarmService, Depends(get_farm_service)]

SensorServiceDependency = Annotated[SensorService, Depends(get_sensor_service)]