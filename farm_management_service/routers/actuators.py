from fastapi import APIRouter, Path, Query, status

from farm_management_service.dependencies import (
    ActuatorServiceDependency,
    CurrentUserDependency,
)
from farm_management_service.schemas import (
    ActuatorPagination,
    ActuatorRead,
    ActuatorUpdate,
)

router = APIRouter(prefix="/actuators", tags=["Actuators"])


@router.get(
    "/actuator/{actuator_id}",
    status_code=status.HTTP_200_OK,
    response_model=ActuatorRead,
)
async def get(
    actuator_service: ActuatorServiceDependency,
    current_user: CurrentUserDependency,
    actuator_id: str = Path(max_length=100),
) -> ActuatorRead:
    actuator_entity = await actuator_service.get(actuator_id)
    await actuator_service.check_access(actuator_entity, current_user)
    return actuator_entity


@router.get("/all", status_code=status.HTTP_200_OK, response_model=ActuatorPagination)
async def all(
    actuator_service: ActuatorServiceDependency,
    current_user: CurrentUserDependency,
    sort_column: str | None = None,
    cursor: str | None = Query(None),
    limit: int | None = Query(10, ge=10, le=200),
) -> ActuatorPagination:
    items, next_cursor = await actuator_service.get_all_actuators(
        current_user.id, sort_column, cursor, limit
    )
    return {"items": items, "next_cursor": next_cursor}


@router.put(
    "/actuator/{actuator_id}",
    status_code=status.HTTP_200_OK,
    response_model=ActuatorRead,
)
async def update(
    actuator: ActuatorUpdate,
    actuator_service: ActuatorServiceDependency,
    current_user: CurrentUserDependency,
    actuator_id: str = Path(max_length=100),
) -> ActuatorRead:
    actuator_entity = await actuator_service.get(actuator_id)
    await actuator_service.check_access(actuator_entity, current_user)
    new_actuator_entity = await actuator_service.update(
        actuator_entity, **actuator.model_dump(exclude_unset=True)
    )
    return new_actuator_entity


@router.delete("/actuator/{actuator_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    actuator_service: ActuatorServiceDependency,
    current_user: CurrentUserDependency,
    actuator_id: str = Path(max_length=100),
):
    actuator_entity = await actuator_service.get(actuator_id)
    await actuator_service.delete(actuator_entity)
