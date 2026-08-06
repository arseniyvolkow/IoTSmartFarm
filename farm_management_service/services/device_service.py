
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from starlette import status

from common.auth.schemas import CurrentUser
from farm_management_service.enums import AccessLevel
from farm_management_service.models import Devices
from farm_management_service.repositories.actuator_repository import ActuatorRepository
from farm_management_service.repositories.device_repository import DeviceRepository
from farm_management_service.repositories.sensor_repository import SensorRepository
from farm_management_service.schemas import DeviceCreate, DevicePagination, DeviceRead
from farm_management_service.services.access_service import AccessService


class DeviceService:
    def __init__(
        self,
        device_repo: DeviceRepository,
        sensor_repo: SensorRepository,
        actuator_repo: ActuatorRepository,
        access_service: AccessService
    ):
        self.device_repo = device_repo
        self.sensor_repo = sensor_repo
        self.actuator_repo = actuator_repo
        self.access_service = access_service

    async def check_access(self, entity, user: CurrentUser | str, required_level: AccessLevel = AccessLevel.READ):
        user_id = user
        
        # 1. Check Global Permissions (RBAC Override)
        if isinstance(user, CurrentUser):
            user_id = user.id
            g_perms = user.g_perms or {}
            if g_perms.get("w_all") is True:
                return # Admin Write
            if g_perms.get("r_all") is True and required_level == AccessLevel.READ:
                return # Admin Read

        # 2. Direct Ownership
        if entity.user_id == user_id:
            return

        # 3. Farm Access
        farm_id = getattr(entity, "farm_id", None)
        if farm_id:
            has_perm = await self.access_service.has_access(farm_id, user_id, required_level)
            if has_perm:
                return

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied!"
        )

    async def get(self, device_id: str) -> Devices:
        device = await self.device_repo.get_by_id(device_id)
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
            )
        return device

    async def create(self, device_data: DeviceCreate) -> DeviceRead:
        # 1. Check if device already exists
        existing_device = await self.device_repo.get_by_unique_id(device_data.unique_device_id)

        if existing_device:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Device already exists!"
            )

        # 2. Create the main device object
        device_entity = await self.device_repo.create_and_flush(device_data)

        try:
            device_id = str(device_entity.__dict__["device_id"])
        except KeyError:
            device_id = await self.device_repo.get_device_id_by_unique_id(device_data.unique_device_id)

        # 3. Use the dedicated repos to stage sensors and actuators
        self.sensor_repo.add_sensors_to_session(
            device_id=device_id,
            sensors_list=device_data.sensors_list,
        )
        self.actuator_repo.add_actuators_to_session(
            device_id=device_id,
            actuators_list=device_data.actuators_list,
        )

        # 4. Commit everything in a single atomic transaction
        try:
            await self.device_repo.commit()
        except IntegrityError:
            await self.device_repo.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A database integrity error occurred. The device ID might already exist.",
            )
        except Exception as e:
            await self.device_repo.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred: {e!s}",
            )
        return await self.get(device_id)

    async def get_unassigned_to_user_devices(
        self,
        sort_column: str,
        cursor: str | None = None,
        limit: int | None = 10,
    ):
        items, next_cursor = await self.device_repo.get_unassigned_to_user_devices(sort_column, cursor, limit)
        return items, next_cursor

    async def get_unassigned_to_farm_devices(
        self,
        user_id: str,
        sort_column: str,
        cursor: str | None = None,
        limit: int | None = 10,
    ):
        items, next_cursor = await self.device_repo.get_unassigned_to_farm_devices(user_id, sort_column, cursor, limit)
        return items, next_cursor

    async def get_user_devices(
        self,
        user_id: str,
        sort_column: str,
        farm_id: str | None = None,
        cursor: str | None = None,
        limit: int | None = 10,
    ) -> DevicePagination:
        items, next_cursor = await self.device_repo.get_user_devices(user_id, sort_column, farm_id, cursor, limit)
        return items, next_cursor

    async def update(self, device_entity: Devices, **kwargs) -> Devices:
        return await self.device_repo.update(device_entity, **kwargs)

    async def delete(self, device_entity: Devices):
        await self.device_repo.delete(device_entity)
