import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List

import httpx
import rule_engine
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

# Локальные импорты
from rule_worker.database import get_db, engine
from rule_worker.models import Rules, RuleTriggerType, Base
from rule_worker.services.redis_service import RedisService
from rule_worker.services.action_executor import ActionExecutor

logger = logging.getLogger(__name__)


class RuleWorker:
    """Rule evaluation engine."""

    def __init__(self, redis_service: RedisService, http_client: Optional[httpx.AsyncClient] = None):
        self.redis_service = redis_service
        self._owns_http_client = http_client is None
        self.http_client = http_client or httpx.AsyncClient(timeout=30.0)
        
        # Instantiate the ActionExecutor and pass dependencies
        sensor_service_url = os.getenv("SENSOR_DATA_SERVICE_HOST", "http://sensor_data_service:8000")
        self.action_executor = ActionExecutor(self.http_client, sensor_service_url)

    async def close(self):
        """Clean up resources."""
        if self._owns_http_client:
            await self.http_client.aclose()
            logger.info("HTTP client closed")

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

    async def _prepare_context(self, rule: Rules, triggered_value: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Prepare the context dictionary for rule evaluation."""
        now = datetime.now(timezone.utc)
        context = {
            "rule_id": rule.rule_id,
            "rule_name": rule.rule_name,
            "current_time": now.isoformat(),
        }

        if rule.trigger_type == RuleTriggerType.SENSOR_THRESHOLD:
            if not rule.sensor_id:
                logger.warning(f"Rule '{rule.rule_name}' is missing sensor_id.")
                return None
            
            value = triggered_value
            if value is None:
                sensor_data = await self.redis_service.get_json(rule.sensor_id)
                if sensor_data is None:
                    # Fallback to raw string value
                    raw_val = await self.redis_service.get(rule.sensor_id)
                    if raw_val is not None:
                        try:
                            value = float(raw_val)
                        except ValueError:
                            pass
                elif isinstance(sensor_data, dict) and "value" in sensor_data:
                    value = float(sensor_data["value"])
                else:
                    try:
                        value = float(sensor_data)
                    except (ValueError, TypeError):
                        pass

            if value is None:
                logger.debug(f"No valid data for sensor {rule.sensor_id}. Skipping.")
                return None
            
            context["value"] = value
            context["sensor_id"] = rule.sensor_id

        elif rule.trigger_type == RuleTriggerType.TIME_BASED:
            # For time-based rules, use local time for easier rule writing (e.g., "hour == 8")
            local_now = datetime.now()
            context.update({
                "hour": local_now.hour, "minute": local_now.minute, "day_of_week": local_now.weekday(),
                "day": local_now.day, "month": local_now.month, "year": local_now.year,
            })
        else:
            logger.warning(f"Unsupported trigger type for rule '{rule.rule_name}'.")
            return None
        
        return context

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
            stmt = update(Rules).where(Rules.rule_id == rule.rule_id).values(last_triggered_at=datetime.now(timezone.utc))
            await db.execute(stmt)
            await db.commit()
            logger.info(f"📝 Rule '{rule.rule_name}' last_triggered_at updated.")
        except SQLAlchemyError as e:
            logger.error(f"Failed to update last_triggered_at for rule {rule.rule_id}: {e}")
            await db.rollback()

    async def evaluate_single_rule(self, rule: Rules, db_session: AsyncSession, triggered_value: Optional[float] = None) -> bool:
        """Evaluate a single rule."""
        if self._is_rule_on_cooldown(rule):
            return False

        try:
            context = await self._prepare_context(rule, triggered_value=triggered_value)
            if context is None:
                return False

            rule_engine_obj = rule_engine.Rule(rule.rule_expression)
            
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
            query = select(Rules).options(joinedload(Rules.actions)).where(Rules.is_active == True)
            if trigger_type:
                query = query.where(Rules.trigger_type == trigger_type)
            
            result = await db_session.execute(query)
            rules = result.scalars().unique().all()

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
            query = (
                select(Rules)
                .options(joinedload(Rules.actions))
                .where(Rules.is_active == True)
                .where(Rules.trigger_type == RuleTriggerType.SENSOR_THRESHOLD)
                .where(Rules.sensor_id == sensor_id)
            )
            
            result = await db_session.execute(query)
            rules = result.scalars().unique().all()

            if not rules:
                return

            logger.info(f"🎯 Evaluating {len(rules)} rules for updated sensor: {sensor_id} (value: {value})")
            
            tasks = [self.evaluate_single_rule(rule, db_session, triggered_value=value) for rule in rules]
            await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"❌ Error evaluating rules for sensor {sensor_id}: {e}", exc_info=True)

    async def listen_for_sensor_updates(self):
        """Listen to Redis Pub/Sub for real-time sensor updates."""
        logger.info("📡 Starting real-time sensor update listener...")
        
        while True:
            pubsub = None
            try:
                pubsub = await self.redis_service.subscribe_to_channel("sensor_updates")
                if not pubsub:
                    await asyncio.sleep(5)
                    continue

                async for message in pubsub.listen():
                    if message["type"] == "message":
                        try:
                            logger.info(f"📩 Received sensor update: {message['data']}")
                            data = json.loads(message["data"])
                            sensor_id = data.get("sensor_id")
                            value = data.get("value")
                            
                            if sensor_id is not None and value is not None:
                                try:
                                    val_float = float(value)
                                    async with get_db() as db_session:
                                        await self.evaluate_rules_for_sensor(sensor_id, val_float, db_session)
                                except ValueError:
                                    logger.warning(f"Received non-numeric value for sensor {sensor_id}: {value}")
                        except json.JSONDecodeError:
                            logger.error(f"Failed to decode sensor update message: {message['data']}")
                        except Exception as e:
                            logger.error(f"Error processing sensor update: {e}", exc_info=True)
            
            except Exception as e:
                logger.error(f"❌ Error in Pub/Sub listener: {e}", exc_info=True)
                await asyncio.sleep(5)
            finally:
                if pubsub:
                    try:
                        await pubsub.unsubscribe("sensor_updates")
                    except:
                        pass

async def run_periodic_evaluation(rule_worker: RuleWorker, interval_seconds: int):
    """Run periodic evaluation for time-based rules."""
    logger.info(f"🔄 Starting periodic evaluation (every {interval_seconds}s)")
    while True:
        try:
            async with get_db() as db_session:
                # We mainly care about TIME_BASED rules in the periodic cycle now,
                # as SENSOR_THRESHOLD rules are handled by Pub/Sub.
                # However, we can still check all rules periodically as a fallback.
                await rule_worker.evaluate_all_rules(db_session)
            
            await asyncio.sleep(interval_seconds)
        except Exception as e:
            logger.error(f"Error in periodic evaluation task: {e}")
            await asyncio.sleep(10)

async def run_rule_worker_daemon(interval_seconds: int = 60):
    """
    Run the rule worker with both periodic and real-time evaluation.
    """
    logger.info(f"🚀 Starting rule worker daemon")

    redis_service = None
    rule_worker = None

    try:
        # 1. Initialize Redis Service
        redis_service = RedisService(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            password=os.getenv("REDIS_PASSWORD"),
        )

        await redis_service.connect()
        logger.info("✅ Redis connected successfully")

        # 2. Create RuleWorker
        rule_worker = RuleWorker(redis_service=redis_service)
        logger.info("✅ RuleWorker initialized")

        # 3. Start concurrent tasks
        tasks = [
            asyncio.create_task(run_periodic_evaluation(rule_worker, interval_seconds)),
            asyncio.create_task(rule_worker.listen_for_sensor_updates())
        ]

        await asyncio.gather(*tasks)

    except asyncio.CancelledError:
        logger.info("⚠️  Daemon tasks cancelled")
    except Exception as e:
        logger.critical(f"🚨 Fatal error in rule worker daemon: {e}", exc_info=True)
        raise

    finally:
        logger.info("\n🧹 Starting cleanup...")
        if rule_worker:
            await rule_worker.close()
        if redis_service:
            await redis_service.disconnect()
        logger.info("👋 Rule worker daemon shut down complete")