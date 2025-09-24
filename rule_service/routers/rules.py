from fastapi import APIRouter, Depends, Query, Path, status
from ..database import get_db
from typing import Annotated, Optional
from sqlalchemy.orm import Session
from ..services.rules_service import RulesService
from ..schemas import RuleCreate, RuleUpdate
from ..utils import get_current_user


router = APIRouter(prefix="/rules", tags=["Rules and Actions"])
db_dependency = Annotated[Session, Depends(get_db)]


@router.post("/rule", status_code=status.HTTP_201_CREATED)
async def add_new_rule(
    db: db_dependency,
    current_user: Annotated[dict, Depends(get_current_user)],
    rule: RuleCreate,
):
    rule_service = RulesService(db)
    await rule_service.create(rule, current_user["id"])
    return {"message": "Rule added successfully"}


@router.get("/rule", status_code=status.HTTP_200_OK)
async def get_rule_by_id(
    db: db_dependency, rule_id, current_user: Annotated[dict, Depends(get_current_user)]
):
    rule_service = RulesService(db)
    rule_entity = await rule_service.get(rule_id)
    await rule_service.check_access(rule_entity, current_user["id"])
    return rule_entity


@router.get("/all", status_code=status.HTTP_200_OK)
async def get_all_rules(
    db: db_dependency,
    current_user: Annotated[dict, Depends(get_current_user)],
    sort_column: str,
    cursor: Optional[str] = Query(None),
    limit: Optional[int] = Query(10, le=200),
    farm_id: Optional[str] = None,
    sensor_id: Optional[str] = None,
    trigger_type: Optional[str] = None,
):
    rule_service = RulesService(db)
    items, next_cursor = await rule_service.get_all(
        current_user["id"], sort_column, farm_id, sensor_id, trigger_type, cursor, limit
    )
    return {"items": items, "next_cursor": next_cursor}


@router.put("/rule/{rule_id}", status_code=status.HTTP_200_OK)
async def update_rule(
    db: db_dependency,
    rule: RuleUpdate,
    current_user: Annotated[dict, Depends(get_current_user)],
    farm_id: str = Path(max_length=100),
):
    rule_service = RulesService(db)
    rule_entity = await rule_service.get(farm_id)
    await rule_service.check_access(rule_entity, current_user["id"])
    await rule_service.update(rule_entity, **rule.model_dump())
    return {"details": f"Rule {rule_entity.rule_id} info was updated!"}


@router.delete("/rule/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    db: db_dependency,
    current_user: Annotated[dict, Depends(get_current_user)],
    rule_id: str = Path(max_length=100),
):
    rule_service = RulesService(db)
    rule_entity = await rule_service.get(rule_id)
    await rule_service.check_access()
    await rule_service.delete()
