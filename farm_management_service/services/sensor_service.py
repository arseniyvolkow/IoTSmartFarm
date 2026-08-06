from fastapi import HTTPException, status

from common.auth.schemas import CurrentUser
from farm_management_service.enums import AccessLevel
from farm_management_service.models import Sensors
from farm_management_service.repositories.sensor_repository import SensorRepository
from farm_management_service.schemas import SensorBase, SensorRead
from farm_management_service.services.access_service import AccessService


class SensorService:
    def __init__(self, sensor_repo: SensorRepository, access_service: AccessService):
        self.sensor_repo = sensor_repo
        self.access_service = access_service

    async def check_access(
        self,
        entity,
        user: CurrentUser | str,
        required_level: AccessLevel = AccessLevel.READ,
    ):
        user_id = user

        # 1. Check Global Permissions (RBAC Override)
        if isinstance(user, CurrentUser):
            user_id = user.id
            g_perms = user.g_perms or {}
            if g_perms.get("w_all") is True:
                return  # Admin Write
            if g_perms.get("r_all") is True and required_level == AccessLevel.READ:
                return  # Admin Read

        # 2. Direct Ownership (Sensor)
        if getattr(entity, "user_id", None) == user_id:
            return

        # 3. Device Ownership
        if entity.device and entity.device.user_id == user_id:
            return

        # 4. Farm Access
        device = entity.device
        if device and device.farm_id:
            has_perm = await self.access_service.has_access(
                device.farm_id, user_id, required_level
            )
            if has_perm:
                return

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied!"
        )

    def add_sensors_to_session(self, device_id: str, sensors_list: list[SensorBase]):
        self.sensor_repo.add_sensors_to_session(device_id, sensors_list)

    async def get(self, sensor_id: str) -> Sensors:
        sensor = await self.sensor_repo.get_by_id(sensor_id)
        if not sensor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Sensor not found"
            )
        return sensor

    async def get_all_sensors(
        self,
        user_id: str,
        sort_column: str,
        cursor: str | None = None,
        limit: int | None = 10,
    ) -> tuple[list[SensorRead], str | None]:
        items, next_cursor = await self.sensor_repo.get_all_sensors(
            user_id, sort_column, cursor, limit
        )
        pydantic_items = [SensorRead.model_validate(item) for item in items]
        return pydantic_items, next_cursor

    async def assign_user_to_device_sensors(self, device_id: str, user_id: str):
        await self.sensor_repo.assign_user_to_device_sensors(device_id, user_id)

    async def update(self, sensor_entity: Sensors, **kwargs) -> Sensors:
        return await self.sensor_repo.update(sensor_entity, **kwargs)

    async def delete(self, sensor_entity: Sensors):
        await self.sensor_repo.delete(sensor_entity)
