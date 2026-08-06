
from fastapi import HTTPException, status

from common.models.rule_models import RuleActions, Rules
from rule_service.repositories.rule_repository import RuleRepository
from rule_service.schemas import RuleCreate
from rule_service.services.rule_validator import RuleValidator


class RulesService:
    def __init__(self, rule_repo: RuleRepository, rule_validator: RuleValidator):
        self.rule_repo = rule_repo
        self.rule_validator = rule_validator

    async def create(self, rule: RuleCreate, user_id: str):
        # 1. Validate rule_expression
        self.rule_validator.validate_expression(rule.rule_expression)

        # 2. Create the Rules entity
        rule_entity = Rules(
            farm_id=rule.farm_id,
            user_id=user_id,
            rule_name=rule.rule_name,
            description=rule.description,
            trigger_type=rule.trigger_type,
            sensor_id=rule.sensor_id,
            device_id=rule.device_id,
            rule_expression=rule.rule_expression,
            cooldown_seconds=rule.cooldown_seconds,
            is_active=rule.is_active,
        )

        # 3. Prepare and add RuleActions entities
        rule_actions = []
        from common.models.rule_enums import RuleActionType
        
        for action_data in rule.actions:
            action_payload = action_data.action_payload.model_dump()
            
            # Inject device_id if this is a CONTROL_DEVICE action
            if action_data.action_type == RuleActionType.CONTROL_DEVICE:
                actuators = action_payload.get("actuators_to_control", [])
                for act in actuators:
                    if "actuator_id" in act and "device_id" not in act:
                        device_id = await self.rule_repo.get_device_id_for_actuator(act["actuator_id"])
                        if device_id:
                            act["device_id"] = device_id
                            
            action_entity = RuleActions(
                action_type=action_data.action_type,
                action_payload=action_payload,
                execution_order=action_data.execution_order,
            )
            rule_actions.append(action_entity)

        rule_entity.actions = rule_actions

        # 4. Delegate to repository to save
        return await self.rule_repo.create(rule_entity)

    async def get(self, rule_id: str) -> Rules:
        rule_entity = await self.rule_repo.get_by_id(rule_id)
        if not rule_entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found"
            )
        return rule_entity

    async def get_all(
        self,
        user_id: str,
        sort_column: str,
        farm_id: str | None = None,
        sensor_id: str | None = None,
        trigger_type: str | None = None,
        cursor: str | None = None,
        limit: int | None = 10,
    ):
        items, next_cursor = await self.rule_repo.get_all(
            user_id, sort_column, farm_id, sensor_id, trigger_type, cursor, limit
        )
        return items, next_cursor

    async def check_access(self, entity: Rules, user_id: str):
        # Delegate to base repository check
        await self.rule_repo.check_access(entity, user_id)

    async def update(self, rule_entity: Rules, **kwargs):
        await self.rule_repo.update(rule_entity, **kwargs)

    async def delete(self, rule_entity: Rules):
        await self.rule_repo.delete(rule_entity)