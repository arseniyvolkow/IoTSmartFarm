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
from farm_management_service.services.access_service import AccessService

from farm_management_service.repositories.actuator_repository import ActuatorRepository
from farm_management_service.repositories.crop_repository import CropRepository
from farm_management_service.repositories.device_repository import DeviceRepository
from farm_management_service.repositories.farm_repository import FarmRepository
from farm_management_service.repositories.sensor_repository import SensorRepository
from farm_management_service.repositories.access_repository import AccessRepository

db_dependency = Annotated[AsyncSession, Depends(get_db)]

def get_access_service(db: db_dependency) -> AccessService:
    repo = AccessRepository(db)
    return AccessService(repo)

def get_actuator_service(db: db_dependency, access_service: AccessService = Depends(get_access_service)) -> ActuatorService:
    repo = ActuatorRepository(db)
    return ActuatorService(repo, access_service)

def get_crop_service(db: db_dependency, access_service: AccessService = Depends(get_access_service)) -> CropService:
    repo = CropRepository(db)
    return CropService(repo, access_service)

def get_device_service(db: db_dependency, access_service: AccessService = Depends(get_access_service)) -> DeviceService:
    device_repo = DeviceRepository(db)
    sensor_repo = SensorRepository(db)
    actuator_repo = ActuatorRepository(db)
    return DeviceService(device_repo, sensor_repo, actuator_repo, access_service)

def get_farm_service(db: db_dependency, access_service: AccessService = Depends(get_access_service)) -> FarmService:
    repo = FarmRepository(db)
    return FarmService(repo, access_service)

def get_sensor_service(db: db_dependency, access_service: AccessService = Depends(get_access_service)) -> SensorService:
    repo = SensorRepository(db)
    return SensorService(repo, access_service)

CurrentUserDependency = Annotated[CurrentUser, Depends(get_current_user_identity)]
DeviceServiceDependency = Annotated[DeviceService, Depends(get_device_service)]
CropServiceDependency = Annotated[CropService, Depends(get_crop_service)]
FarmServiceDependency = Annotated[FarmService, Depends(get_farm_service)]
SensorServiceDependency = Annotated[SensorService, Depends(get_sensor_service)]