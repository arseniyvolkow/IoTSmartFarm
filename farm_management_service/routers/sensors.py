from fastapi import APIRouter, status, Query, Path
from farm_management_service.schemas import SensorRead, SensorUpdate, SensorPagination
from typing import Optional
from farm_management_service.dependencies import db_dependency, CurrentUserDependency
from farm_management_service.services.sensor_service import SensorService


router = APIRouter(prefix="/sensors", tags=["Sensors"])


@router.get(
    "/sensor/{sensor_id}", status_code=status.HTTP_200_OK, response_model=SensorRead
)
async def get(
    db: db_dependency,
    current_user: CurrentUserDependency,
    sensor_id: str = Path(max_length=100),
) -> SensorRead:
    sensor_service = SensorService(db)
    sensor_entity = await sensor_service.get(sensor_id)
    await sensor_service.check_access(sensor_entity, current_user.id)
    return sensor_entity


@router.get("/all", status_code=status.HTTP_200_OK, response_model=SensorPagination)
async def all(
    db: db_dependency,
    current_user: CurrentUserDependency,
    sort_column: Optional[str] = None,
    cursor: Optional[str] = Query(None),
    limit: Optional[int] = Query(10, ge=10, le=200),
):
    sensor_service = SensorService(db)
    items, next_cursor = await sensor_service.get_all_sensors(
        current_user.id, sort_column, cursor, limit
    )
    return {"items": items, "next_cursor": next_cursor}


@router.put("/sensor/{sensor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update(
    db: db_dependency,
    sensor: SensorUpdate,
    current_user: CurrentUserDependency,
    sensor_id: str = Path(max_length=100),
):
    sensor_service = SensorService(db)
    sensor_entity = await sensor_service.get(sensor_id)
    await sensor_service.check_access(sensor_entity, current_user.id)
    await sensor_service.update(sensor_entity, **sensor.model_dump())
    return {"details": f"Farm {sensor_entity.sensor_id} info was updated!"}


@router.delete("/sensor/{sensor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    db: db_dependency,
    current_user: CurrentUserDependency,
    sensor_id: str = Path(max_length=100),
):
    sensor_service = SensorService(db)
    sensor_entity = await sensor_service.get(sensor_id)
    #await sensor_service.check_access(sensor_entity, current_user.id)
    await sensor_service.delete(sensor_entity)
    return {"details": f"Farm {sensor_entity.sensor_id} was deleted"}
