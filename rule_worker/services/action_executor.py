import json
import logging
from typing import Dict, Any, Callable, Awaitable, Optional
from rule_worker.enums import RuleActionType
from rule_worker.services.redis_service import RedisService

logger = logging.getLogger(__name__)

class ActionExecutor:
    """
    Dispatcher service to execute rule actions.
    Integrates with other microservices via Redis Pub/Sub instead of synchronous HTTP calls.
    """

    def __init__(self, redis_service: RedisService):
        self.redis_service = redis_service
        
        # Mapping RuleActionType (from rule_worker.enums) to handler methods
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Awaitable[bool]]] = {
            RuleActionType.CONTROL_DEVICE.value: self._execute_device_control,
            RuleActionType.SEND_NOTIFICATION.value: self._execute_notification_placeholder,
            RuleActionType.LOG_EVENT.value: self._execute_log_message,
        }

    async def execute(self, action_dict: Dict[str, Any], context: Dict[str, Any] = None) -> bool:
        """
        Executes an action based on its type using the handler map.
        """
        action_type = action_dict.get("action_type")
        action_id = action_dict.get("action_id", "unknown")
        action_payload = action_dict.get("action_payload", {})

        handler = self._handlers.get(action_type)

        if not handler:
            logger.warning(f"⚠️ Unknown action type '{action_type}' for action ID {action_id}")
            return False

        logger.info(f"▶️ Executing action {action_id} [{action_type}]")
        
        try:
            # Pass context if needed by handlers in the future
            result = await handler(action_payload)
            if result:
                logger.info(f"✅ Action {action_id} completed successfully.")
            else:
                logger.warning(f"⚠️ Action {action_id} failed or returned False.")
            return result
        except Exception as e:
            logger.error(f"❌ Critical error executing action {action_id}: {e}", exc_info=True)
            return False

    async def _execute_device_control(self, payload: Dict[str, Any]) -> bool:
        """
        Publishes an actuator command to Redis asynchronously.
        Expected payload in DB: {"actuators_to_control": [{"actuator_id": "...", "command": "..."}]}
        """
        actuators = payload.get("actuators_to_control")
        if not actuators:
            logger.warning("Action payload missing 'actuators_to_control'. Skipping.")
            return False

        control_payload = {"actuators_to_control": actuators}
        
        try:
            message = json.dumps(control_payload)
            # Publishing to the 'actuator_commands' Redis channel
            result = await self.redis_service.publish("actuator_commands", message)
            logger.debug(f"Published to actuator_commands: {message}")
            return result is not None
        except Exception as e:
            logger.error(f"❌ Error publishing device control command: {e}")
            return False

    async def _execute_notification_placeholder(self, payload: Dict[str, Any]) -> bool:
        """
        Placeholder for sending notifications (e.g., Email, SMS, Push).
        """
        logger.info(f"🔔 [MOCK] Notification triggered with payload: {payload}")
        return True

    async def _execute_log_message(self, payload: Dict[str, Any]) -> bool:
        """
        Internal logging action.
        """
        message = payload.get("message", "Rule triggered")
        level_str = payload.get("level", "INFO").upper()
        
        log_method = getattr(logger, level_str.lower(), logger.info)
        log_method(f"📝 RULE LOG: {message}")
        return True
