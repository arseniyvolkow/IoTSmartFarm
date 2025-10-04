from ..utils import BaseService
from ..models import Rules, RuleActions
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from typing import Optional
from fastapi import HTTPException
from ..schemas import RuleCreate
from fastapi import status
from ..enums import RuleTriggerType

class RulesService(BaseService):

    async def create(self, rule: RuleCreate, user_id):
        # 1. Create the Rules entity
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

        # 2. Prepare and add RuleActions entities
        rule_actions = []
        for action_data in rule.actions:
            action_entity = RuleActions(
                action_type=action_data.action_type,
                action_payload=action_data.action_payload.model_dump(),  # Use model_dump() to convert Pydantic model to dict
                execution_order=action_data.execution_order,
                # rule_id is not explicitly set here; SQLAlchemy handles this via the relationship
            )
            rule_actions.append(action_entity)

        # 3. Assign the list of RuleActions entities to the 'actions' relationship attribute
        # SQLAlchemy will correctly link these actions to the rule_entity upon commit
        rule_entity.actions = rule_actions

        # 4. Add the parent entity (Rules) to the session
        self.db.add(rule_entity)

        # 5. Commit the transaction
        # Both the rule and all associated actions are saved to the database
        await self.db.commit()

        # 6. Refresh the entity to ensure all generated fields (like action_id) are loaded
        await self.db.refresh(rule_entity)

        return rule_entity

    async def get(self, rule_id) -> Rules:
        query = (
            select(Rules)
            .filter(Rules.rule_id == rule_id)
            .options(joinedload(Rules.actions), joinedload(Rules.triggered_alerts))
        )
        result = await self.db.execute(query)
        rule_entity = result.scalar_one_or_none()
        if not rule_entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found"
            )
        return rule_entity

    async def get_all(
        self,
        user_id,
        sort_column: str,
        farm_id: Optional[str] = None,
        sensor_id: Optional[str] = None,
        trigger_type: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = 10,
    ):
        # 1. Start the query and filter by user_id
        query = select(Rules).filter(Rules.user_id == user_id)
        
        # 2. Eager-load the 'actions' relationship
        # This executes a JOIN in the database query to fetch the rule and all its actions simultaneously.
        query = query.options(joinedload(Rules.actions))
        
        # 3. Apply optional filters
        if farm_id:
            query = query.filter(Rules.farm_id == farm_id)
        if sensor_id:
            query = query.filter(Rules.sensor_id == sensor_id)
        # Note: We must compare RuleTriggerType enum to RuleTriggerType enum
        if trigger_type:
            # Assuming trigger_type is a string that needs conversion to the Enum type
            try:
                trigger_enum = RuleTriggerType(trigger_type)
                query = query.filter(Rules.trigger_type == trigger_enum)
            except ValueError:
                # Handle case where the provided trigger_type string is invalid, or just ignore the filter
                pass


        items, next_cursor = await self.cursor_paginate(
            self.db, query, sort_column, cursor, limit
        )
        return items, next_cursor