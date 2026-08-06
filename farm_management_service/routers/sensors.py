
from fastapi import APIRouter, Path, Query, status

from farm_management_service.dependencies import (
    CurrentUserDependency,
    SensorServiceDependency,
)
from farm_management_service.schemas import SensorPagination, SensorRead, SensorUpdate

router = APIRouter(prefix="/sensors", tags=["Sensors"])


@router.get(
    "/sensor/{sensor_id}", status_code=status.HTTP_200_OK, response_model=SensorRead
)
async def get(
    sensor_service: SensorServiceDependency,
    current_user: CurrentUserDependency,
    sensor_id: str = Path(max_length=100),
) -> SensorRead:
    sensor_entity = await sensor_service.get(sensor_id)
    await sensor_service.check_access(sensor_entity, current_user)
    return sensor_entity


@router.get("/all", status_code=status.HTTP_200_OK, response_model=SensorPagination)
async def all(
    sensor_service: SensorServiceDependency,
    current_user: CurrentUserDependency,
    sort_column: str | None = None,
    cursor: str | None = Query(None),
    limit: int | None = Query(10, ge=10, le=200),
):
    items, next_cursor = await sensor_service.get_all_sensors(
        current_user.id, sort_column, cursor, limit
    )
    return {"items": items, "next_cursor": next_cursor}


@router.put("/sensor/{sensor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update(
    sensor: SensorUpdate,
    sensor_service: SensorServiceDependency,
    current_user: CurrentUserDependency,
    sensor_id: str = Path(max_length=100),
):
    sensor_entity = await sensor_service.get(sensor_id)
    await sensor_service.check_access(sensor_entity, current_user)
    await sensor_service.update(sensor_entity, **sensor.model_dump(exclude_unset=True))
    return {"details": f"Farm {sensor_entity.sensor_id} info was updated!"}


@router.delete("/sensor/{sensor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    sensor_service: SensorServiceDependency,
    current_user: CurrentUserDependency,
    sensor_id: str = Path(max_length=100),
):
    sensor_entity = await sensor_service.get(sensor_id)
    await sensor_service.delete(sensor_entity)
    return {"details": f"Farm {sensor_entity.sensor_id} was deleted"}