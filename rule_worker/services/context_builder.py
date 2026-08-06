import logging
from datetime import datetime, timezone
from typing import Any

from common.models.rule_models import Rules, RuleTriggerType
from rule_worker.services.redis_service import RedisService

logger = logging.getLogger(__name__)

class RuleContextBuilder:
    def __init__(self, redis_service: RedisService):
        self.redis_service = redis_service

    async def build(self, rule: Rules, triggered_value: float | None = None) -> dict[str, Any] | None:
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
