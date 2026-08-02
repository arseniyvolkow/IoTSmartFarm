import asyncio
import logging
import functools
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

import rule_engine
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from common.rule_models import Rules, RuleTriggerType
from rule_worker.services.action_executor import ActionExecutor
from rule_worker.services.context_builder import RuleContextBuilder
from rule_worker.services.rule_cache import rule_cache

logger = logging.getLogger(__name__)

@functools.lru_cache(maxsize=10000)
def _compile_rule(expression: str) -> rule_engine.Rule:
    """
    Compiles a rule expression into an AST. 
    Uses an LRU cache to prevent memory exhaustion while avoiding recompilation overhead.
    """
    return rule_engine.Rule(expression)


class RuleEvaluator:
    """Rule evaluation engine."""
    def __init__(self, action_executor: ActionExecutor, context_builder: RuleContextBuilder):
        self.action_executor = action_executor
        self.context_builder = context_builder

    def _is_rule_on_cooldown(self, rule: Rules) -> bool:
        """Check if the rule is currently on cooldown."""
        if not rule.last_triggered_at:
            return False

        now = datetime.now(timezone.utc)
        
        # Ensure last_triggered_at is offset-aware
        last_triggered = rule.last_triggered_at
        if last_triggered.tzinfo is None:
            last_triggered = last_triggered.replace(tzinfo=timezone.utc)
        else:
            last_triggered = last_triggered.astimezone(timezone.utc)
        
        time_since_triggered = now - last_triggered
        is_on_cooldown = time_since_triggered < timedelta(seconds=rule.cooldown_seconds)

        if is_on_cooldown:
            logger.debug(f"Rule '{rule.rule_name}' (ID: {rule.rule_id}) is on cooldown. Skipping.")
        return is_on_cooldown

    async def _execute_matched_rule_actions(self, rule: Rules, context: Dict[str, Any], db: AsyncSession):
        """Execute all actions for a matched rule and update its timestamp."""
        logger.info(f"✅ Rule '{rule.rule_name}' MATCHED! Context: {context}")
        
        sorted_actions = sorted(rule.actions, key=lambda a: a.execution_order or 0)
        logger.info(f"Executing {len(sorted_actions)} actions for '{rule.rule_name}'")
        
        for action in sorted_actions:
            action_dict = {
                "action_id": action.action_id,
                "action_type": action.action_type.value if hasattr(action.action_type, 'value') else action.action_type,
                "action_payload": action.action_payload,
            }
            try:
                success = await self.action_executor.execute(action_dict, context)
                if not success:
                    logger.warning(f"⚠️ Action {action.action_id} failed for rule '{rule.rule_name}'.")
            except Exception as e:
                logger.error(f"❌ Error executing action {action.action_id}: {e}")

        try:
            now_dt = datetime.now(timezone.utc)
            stmt = update(Rules).where(Rules.rule_id == rule.rule_id).values(last_triggered_at=now_dt)
            await db.execute(stmt)
            await db.commit()
            rule.last_triggered_at = now_dt # Update in-memory rule cache instantly
            logger.info(f"📝 Rule '{rule.rule_name}' last_triggered_at updated.")
        except SQLAlchemyError as e:
            logger.error(f"Failed to update last_triggered_at for rule {rule.rule_id}: {e}")
            await db.rollback()

    async def evaluate_single_rule(self, rule: Rules, db_session: AsyncSession, triggered_value: Optional[float] = None) -> bool:
        """Evaluate a single rule."""
        if self._is_rule_on_cooldown(rule):
            return False

        try:
            context = await self.context_builder.build(rule, triggered_value=triggered_value)
            if context is None:
                return False

            rule_engine_obj = _compile_rule(rule.rule_expression)
            
            if rule_engine_obj.matches(context):
                await self._execute_matched_rule_actions(rule, context, db_session)
                return True

            logger.debug(f"Rule '{rule.rule_name}' (ID: {rule.rule_id}) did not match.")
            return False
            
        except rule_engine.errors.RuleSyntaxError as e:
            logger.error(f"❌ Rule '{rule.rule_name}' (ID: {rule.rule_id}) syntax error: {e}")
        except Exception as e:
            logger.error(f"❌ Error evaluating rule '{rule.rule_name}' (ID: {rule.rule_id}): {e}", exc_info=True)
        
        return False

    async def evaluate_all_rules(self, db_session: AsyncSession, trigger_type: Optional[RuleTriggerType] = None):
        """Evaluate all active rules, optionally filtered by trigger type."""
        try:
            rules = await rule_cache.get_all_rules(trigger_type)

            if not rules:
                return

            logger.info(f"📋 Evaluating {len(rules)} active rules (type: {trigger_type or 'all'})")
            
            tasks = [self.evaluate_single_rule(rule, db_session) for rule in rules]
            await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"❌ Error in evaluation cycle: {e}", exc_info=True)

    async def evaluate_rules_for_sensor(self, sensor_id: str, value: float, db_session: AsyncSession):
        """Evaluate only rules associated with a specific sensor."""
        try:
            rules = await rule_cache.get_rules_for_sensor(sensor_id)

            if not rules:
                return

            logger.info(f"🎯 Evaluating {len(rules)} rules for updated sensor: {sensor_id} (value: {value})")
            
            tasks = [self.evaluate_single_rule(rule, db_session, triggered_value=value) for rule in rules]
            await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"❌ Error evaluating rules for sensor {sensor_id}: {e}", exc_info=True)
