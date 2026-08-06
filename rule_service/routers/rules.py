from fastapi import APIRouter, Path, Query, status

from rule_service.dependencies import CurrentUserDependency, RulesServiceDependency
from rule_service.schemas import RuleCreate, RuleUpdate

router = APIRouter(prefix="/rules", tags=["Rules and Actions"])


@router.post("/rule", status_code=status.HTTP_201_CREATED)
async def add_new_rule(
    rule_service: RulesServiceDependency,
    current_user: CurrentUserDependency,
    rule: RuleCreate,
):
    await rule_service.create(rule, current_user.id)
    return {"message": "Rule added successfully"}


@router.get("/rule/{rule_id}", status_code=status.HTTP_200_OK)
async def get_rule_by_id(
    rule_service: RulesServiceDependency,
    current_user: CurrentUserDependency,
    rule_id: str = Path(max_length=100),
):
    rule_entity = await rule_service.get(rule_id)
    await rule_service.check_access(rule_entity, current_user.id)
    return rule_entity


@router.get("/all", status_code=status.HTTP_200_OK)
async def get_all_rules(
    rule_service: RulesServiceDependency,
    current_user: CurrentUserDependency,
    sort_column: str | None = None,
    cursor: str | None = Query(None),
    limit: int | None = Query(10, le=200),
    farm_id: str | None = None,
    sensor_id: str | None = None,
    trigger_type: str | None = None,
):
    items, next_cursor = await rule_service.get_all(
        current_user.id, sort_column, farm_id, sensor_id, trigger_type, cursor, limit
    )
    return {"items": items, "next_cursor": next_cursor}


@router.put("/rule/{rule_id}", status_code=status.HTTP_200_OK)
async def update_rule(
    rule_service: RulesServiceDependency,
    rule: RuleUpdate,
    current_user: CurrentUserDependency,
    rule_id: str = Path(max_length=100),
):
    rule_entity = await rule_service.get(rule_id)
    await rule_service.check_access(rule_entity, current_user.id)
    await rule_service.update(rule_entity, **rule.model_dump(exclude_unset=True))
    return {"details": f"Rule {rule_entity.rule_id} info was updated!"}


@router.delete("/rule/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_service: RulesServiceDependency,
    current_user: CurrentUserDependency,
    rule_id: str = Path(max_length=100),
):
    rule_entity = await rule_service.get(rule_id)
    await rule_service.check_access(rule_entity, current_user.id)
    await rule_service.delete(rule_entity)
