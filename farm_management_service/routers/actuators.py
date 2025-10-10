from fastapi import APIRouter, status, Query, Path
from typing import Optional
from ..utils import db_dependency, user_dependency
from ..schemas import ActuatorPagination, ActuatorRead, ActuatorUpdate
from ..services.actuators_service import ActuatorService


router = APIRouter(prefix="/actuators", tags=["Actuators"])


@router.get(
    "/actuator/{actuator_id}", status_code=status.HTTP_200_OK, response_model=ActuatorRead
)
async def get(
    db: db_dependency,
    current_user: user_dependency,
    actuator_id: str = Path(max_length=100),
) -> ActuatorRead:
    actuator_service = ActuatorService(db)
    actuator_entity = await actuator_service.get(actuator_id)
    await actuator_service.check_access(actuator_entity, current_user["id"])
    return actuator_entity


@router.get("/all", status_code=status.HTTP_200_OK, response_model=ActuatorPagination)
async def all(
    db: db_dependency,
    current_user: user_dependency,
    sort_column: Optional[str] = None,
    cursor: Optional[str] = Query(None),
    limit: Optional[int] = Query(10, ge=10, le=200),
):
    actuator_service = ActuatorService(db)
    items, next_cursor = await actuator_service.get_all_actuators(
        current_user["id"], sort_column, cursor, limit
    )
    return {"items": items, "next_cursor": next_cursor}


@router.put("/actuator/{actuator_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update(
    db: db_dependency,
    actuator: ActuatorUpdate,
    current_user: user_dependency,
    actuator_id: str = Path(max_length=100),
):
    actuator_service = ActuatorService(db)
    actuator_entity = await actuator_service.get(actuator_id)
    await actuator_service.check_access(actuator_entity, current_user["id"])
    await actuator_service.update(actuator_entity, **actuator.model_dump())
    return {"details": f"Actuator {actuator_entity.actuator_id} info was updated!"}


@router.delete("/actuator/{actuator_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    db: db_dependency,
    current_user: user_dependency,
    actuator_id: str = Path(max_length=100),
):
    actuator_service = ActuatorService(db)
    actuator_entity = await actuator_service.get(actuator_id)
    #await actuator_service.check_access(actuator_entity, current_user["id"])
    await actuator_service.delete(actuator_entity)
    return {"details": f"Farm {actuator_entity.actuator_id} was deleted"}
