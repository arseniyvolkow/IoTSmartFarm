import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

import httpx
import rule_engine
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

# Локальные импорты
from rule_worker.database import get_db
from rule_worker.models import Rules, RuleTriggerType
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
        if rule.last_triggered_at.tzinfo is None:
            last_triggered = rule.last_triggered_at.replace(tzinfo=timezone.utc)
        else:
            last_triggered = rule.last_triggered_at.astimezone(timezone.utc)
        
        time_since_triggered = now - last_triggered
        is_on_cooldown = time_since_triggered < timedelta(seconds=rule.cooldown_seconds)

        if is_on_cooldown:
            logger.debug(f"Rule '{rule.rule_name}' is on cooldown. Skipping.")
        return is_on_cooldown

    async def _prepare_context(self, rule: Rules) -> Optional[Dict[str, Any]]:
        """Prepare the context dictionary for rule evaluation."""
        context = {
            "rule_id": rule.rule_id,
            "rule_name": rule.rule_name,
            "current_time": datetime.now().isoformat(),
        }

        if rule.trigger_type == RuleTriggerType.SENSOR_THRESHOLD:
            if not rule.sensor_id:
                logger.warning(f"Rule '{rule.rule_name}' is missing sensor_id.")
                return None
            
            sensor_data = await self.redis_service.get_json(rule.sensor_id)
            
            if sensor_data is None:
                # Fallback to raw string value
                raw_val = await self.redis_service.get(rule.sensor_id)
                if raw_val is not None:
                    try:
                        context["value"] = float(raw_val)
                        context["sensor_id"] = rule.sensor_id
                        return context
                    except ValueError:
                        pass
                logger.debug(f"No valid data for sensor {rule.sensor_id}. Skipping.")
                return None
            
            if isinstance(sensor_data, dict) and "value" in sensor_data:
                context["value"] = float(sensor_data["value"])
            else:
                try:
                    context["value"] = float(sensor_data)
                except (ValueError, TypeError):
                    return None
            
            context["sensor_id"] = rule.sensor_id

        elif rule.trigger_type == RuleTriggerType.TIME_BASED:
            now = datetime.now()
            context.update({
                "hour": now.hour, "minute": now.minute, "day_of_week": now.weekday(),
                "day": now.day, "month": now.month, "year": now.year,
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
            success = await self.action_executor.execute(action_dict, context)
            if not success:
                logger.warning(f"⚠️ Action {action.action_id} failed for rule '{rule.rule_name}'.")

        try:
            stmt = update(Rules).where(Rules.rule_id == rule.rule_id).values(last_triggered_at=datetime.now(timezone.utc))
            await db.execute(stmt)
            await db.commit()
            logger.info(f"📝 Rule '{rule.rule_name}' last_triggered_at updated.")
        except SQLAlchemyError as e:
            logger.error(f"Failed to update last_triggered_at for rule {rule.rule_id}: {e}")
            await db.rollback()

    async def evaluate_single_rule(self, rule: Rules, db_session: AsyncSession) -> bool:
        """Evaluate a single rule."""
        if self._is_rule_on_cooldown(rule):
            return False

        try:
            context = await self._prepare_context(rule)
            if context is None:
                return False

            rule_engine_obj = rule_engine.Rule(rule.rule_expression)
            
            if rule_engine_obj.matches(context):
                await self._execute_matched_rule_actions(rule, context, db_session)
                return True

            logger.debug(f"Rule '{rule.rule_name}' did not match.")
            return False
            
        except rule_engine.errors.RuleSyntaxError as e:
            logger.error(f"❌ Rule '{rule.rule_name}' syntax error: {e}")
        except Exception as e:
            logger.error(f"❌ Error evaluating rule '{rule.rule_name}': {e}", exc_info=True)
        
        return False

    async def evaluate_rules(self, db_session: AsyncSession):
        """Evaluate all active rules."""
        logger.info(f"[{datetime.now().isoformat()}] Starting rule evaluation cycle")

        if not self.redis_service.is_connected():
            logger.error("❌ Redis not connected. Skipping evaluation.")
            return

        try:
            query = select(Rules).options(joinedload(Rules.actions)).where(Rules.is_active == True)
            result = await db_session.execute(query)
            rules = result.scalars().unique().all()

            if not rules:
                logger.info("No active rules found.")
                return

            logger.info(f"📋 Evaluating {len(rules)} active rules")
            
            tasks = [self.evaluate_single_rule(rule, db_session) for rule in rules]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            triggered_count = sum(1 for res in results if res is True)
            
            logger.info(f"✅ Cycle complete. Evaluated: {len(rules)}, Triggered: {triggered_count}")

        except Exception as e:
            logger.error(f"❌ Critical error in evaluation cycle: {e}", exc_info=True)
        finally:
            logger.info(f"[{datetime.now().isoformat()}] Evaluation cycle finished")

async def run_rule_worker_daemon(interval_seconds: int = 60):
    """
    Run the rule worker continuously with proper dependency management.
    """
    logger.info(f"🚀 Starting rule worker daemon with {interval_seconds}s interval")

    redis_service = None
    rule_worker = None

    try:
        # 1. Initialize Redis Service
        logger.info("📡 Initializing Redis connection...")
        redis_service = RedisService(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            password=os.getenv("REDIS_PASSWORD"),
        )

        await redis_service.connect()
        logger.info("✅ Redis connected successfully")

        if not redis_service.is_connected():
            raise Exception("Redis connection verification failed")

        # 2. Create RuleWorker
        logger.info("⚙️  Initializing RuleWorker...")
        rule_worker = RuleWorker(redis_service=redis_service)
        logger.info("✅ RuleWorker initialized")

        # 3. Main Evaluation Loop
        cycle_count = 0
        logger.info("🔄 Entering main evaluation loop...")

        while True:
            try:
                cycle_count += 1
                logger.info(f"\n{'='*60}")
                logger.info(f"🔄 Starting evaluation cycle #{cycle_count}")
                logger.info(f"{'='*60}")

                async with get_db() as db_session:
                    await rule_worker.evaluate_rules(db_session)

                logger.info(f"{'='*60}")
                logger.info(f"💤 Cycle #{cycle_count} complete. Sleeping for {interval_seconds}s")
                logger.info(f"{'='*60}\n")
                
                await asyncio.sleep(interval_seconds)

            except KeyboardInterrupt:
                logger.info("⚠️  Daemon stopped by user (KeyboardInterrupt)")
                break
            except Exception as e:
                logger.error(f"❌ Error in daemon loop (cycle #{cycle_count}): {e}", exc_info=True)
                logger.info("⏳ Waiting 10 seconds before retry...")
                await asyncio.sleep(10)

    except Exception as e:
        logger.critical(f"🚨 Fatal error during daemon startup: {e}", exc_info=True)
        raise

    finally:
        logger.info("\n🧹 Starting cleanup...")
        if rule_worker:
            await rule_worker.close()
        if redis_service:
            await redis_service.disconnect()
        logger.info("👋 Rule worker daemon shut down complete")