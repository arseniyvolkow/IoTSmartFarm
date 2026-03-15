import logging
import httpx
from typing import Dict, Any, Callable, Awaitable, Optional
from rule_worker.enums import RuleActionType
from rule_worker.services.token_service import TokenService

logger = logging.getLogger(__name__)

class ActionExecutor:
    """
    Dispatcher service to execute rule actions.
    Integrates with other microservices (e.g., Sensor Data Service for actuation).
    """

    def __init__(self, http_client: httpx.AsyncClient, sensor_service_url: str):
        self.http_client = http_client
        self.sensor_service_url = sensor_service_url.rstrip("/")
        self.token_service = TokenService()
        
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

    async def _send_authorized_post_request(self, url: str, payload: Dict[str, Any], context_tag: str) -> bool:
        """Helper to send HTTP POST requests with JWT authentication and standard error handling."""
        
        token = self.token_service.generate_service_token()
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        else:
            logger.warning(f"No authentication token available for '{context_tag}'. Request may fail.")

        try:
            logger.debug(f"Sending POST to {url} | Payload: {payload}")
            response = await self.http_client.post(url, json=payload, headers=headers, timeout=10.0)
            response.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP {e.response.status_code} error during {context_tag}: {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"❌ Connection error during {context_tag}: {e}")
        except Exception as e:
            logger.error(f"❌ Unexpected error during {context_tag}: {e}")
        return False

    async def _execute_device_control(self, payload: Dict[str, Any]) -> bool:
        """
        Calls Sensor Data Service to control actuators.
        Expected payload in DB: {"actuators_to_control": [{"actuator_id": "...", "command": "..."}]}
        Matches sensor_data_service.schemas.ActuatorPayload
        """
        url = f"{self.sensor_service_url}/actuator-mode-update"
        
        # The database payload should ideally match the target API structure
        actuators = payload.get("actuators_to_control")
        if not actuators:
            logger.warning("Action payload missing 'actuators_to_control'. Skipping.")
            return False

        # Prepare the payload according to sensor_data_service schema
        control_payload = {"actuators_to_control": actuators}
        return await self._send_authorized_post_request(url, control_payload, "Device Control")

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
