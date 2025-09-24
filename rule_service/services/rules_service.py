from ..utils import BaseService
from ..models import Rules, RuleActions
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from typing import Optional
from fastapi import HTTPException
from ..schemas import RuleCreate
from fastapi import status


class RulesService(BaseService):

    async def create(self, rule: RuleCreate, user_id):
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

        self.db.add(rule_entity)
        await self.db.commit()
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
        query = select(Rules).filter(Rules.user_id == user_id)
        if farm_id:
            query = query.filter(Rules.farm_id == farm_id)
        if sensor_id:
            query = query.filter(Rules.sensor_id == sensor_id)
        if trigger_type:
            query = query.filter(Rules.trigger_type == trigger_type)

        items, next_cursor = await self.cursor_paginate(
            self.db, query, sort_column, cursor, limit
        )
        return items, next_cursor
