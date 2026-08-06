
from sqlalchemy import select, text
from sqlalchemy.orm import joinedload

from common.models.rule_enums import RuleTriggerType
from common.models.rule_models import Rules
from rule_service.repositories.base_repository import BaseRepository


class RuleRepository(BaseRepository):
    
    async def create(self, rule_entity: Rules) -> Rules:
        self.db.add(rule_entity)
        await self.db.commit()
        await self.db.refresh(rule_entity)
        return rule_entity
        
    async def get_by_id(self, rule_id: str) -> Rules | None:
        query = (
            select(Rules)
            .filter(Rules.rule_id == rule_id)
            .options(joinedload(Rules.actions))
        )
        result = await self.db.execute(query)
        return result.unique().scalar_one_or_none()
        
    async def get_device_id_for_actuator(self, actuator_id: str) -> str | None:
        query = text("SELECT device_id FROM actuators WHERE actuator_id = :actuator_id")
        result = await self.db.execute(query, {"actuator_id": actuator_id})
        return result.scalar_one_or_none()
        
    async def get_all(
        self,
        user_id: str,
        sort_column: str,
        farm_id: str | None = None,
        sensor_id: str | None = None,
        trigger_type: str | None = None,
        cursor: str | None = None,
        limit: int = 10,
    ):
        query = select(Rules).filter(Rules.user_id == user_id)
        query = query.options(joinedload(Rules.actions))
        
        if farm_id:
            query = query.filter(Rules.farm_id == farm_id)
        if sensor_id:
            query = query.filter(Rules.sensor_id == sensor_id)
        if trigger_type:
            try:
                trigger_enum = RuleTriggerType(trigger_type)
                query = query.filter(Rules.trigger_type == trigger_enum)
            except ValueError:
                pass

        return await self.cursor_paginate(
            self.db, query, sort_column, cursor, limit
        )
