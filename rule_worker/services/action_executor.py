import logging
from enum import Enum
from typing import Dict, Any, Callable, Awaitable

import httpx

logger = logging.getLogger(__name__)

class ActionType(str, Enum):
    CONTROL_DEVICE = "CONTROL_DEVICE"
    SEND_NOTIFICATION = "SEND_NOTIFICATION"
    LOG_EVENT = "LOG_EVENT"

class ActionExecutor:
    """
    Dispatcher service to execute rule actions.
    """

    def __init__(self, http_client: httpx.AsyncClient, sensor_service_url: str):
        self.http_client = http_client
        self.sensor_service_url = sensor_service_url.rstrip("/")
        
        # Маппинг типов действий на методы-обработчики
        # Это заменяет длинную цепочку if/elif
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Awaitable[bool]]] = {
            ActionType.CONTROL_DEVICE.value: self._execute_device_control,
            ActionType.SEND_NOTIFICATION.value: self._execute_email_notification,
            ActionType.LOG_EVENT.value: self._execute_log_message,
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
            result = await handler(action_payload)
            if result:
                logger.info(f"✅ Action {action_id} completed successfully.")
            else:
                logger.warning(f"⚠️ Action {action_id} failed or returned False.")
            return result
        except Exception as e:
            # exc_info=True покажет полный стек ошибки в логах
            logger.error(f"❌ Critical error executing action {action_id}: {e}", exc_info=True)
            return False

    async def _send_post_request(self, url: str, payload: Dict[str, Any], context_tag: str) -> bool:
        """Helper to send HTTP POST requests with standard error handling."""
        try:
            logger.debug(f"Sending POST to {url} | Payload: {payload}")
            response = await self.http_client.post(url, json=payload, timeout=10.0)
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
        Calls Sensor Service to control actuators.
        Expected payload: {"devices_to_control": [...]}
        """
        url = f"{self.sensor_service_url}/actuator-mode-update"
        
        devices = payload.get("devices_to_control", [])
        if not devices:
            logger.warning("Action payload missing 'devices_to_control'. Skipping.")
            return False

        control_payload = {"actuators_to_control": devices}
        return await self._send_post_request(url, control_payload, "Device Control")

    async def _execute_email_notification(self, payload: Dict[str, Any]) -> bool:
        """
        Placeholder for sending emails.
        """
        to_email = payload.get("to")
        subject = payload.get("subject", "SmartFarm Alert")
        body = payload.get("body", "")
        
        if not to_email:
            logger.warning("Email action missing 'to' address.")
            return False

        logger.info(f"📧 [MOCK] Sending Email to {to_email} | Subject: {subject}")
        # Здесь можно добавить реальную интеграцию с SMTP или сервисом рассылок
        return True

    async def _execute_log_message(self, payload: Dict[str, Any]) -> bool:
        """
        Internal logging action.
        """
        message = payload.get("message", "Rule triggered")
        level_str = payload.get("level", "INFO").upper()
        
        # Динамически получаем метод логгера (info, warning, error)
        log_method = getattr(logger, level_str.lower(), logger.info)
        log_method(f"📝 RULE LOG: {message}")
        return True