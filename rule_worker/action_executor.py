import logging
from typing import Dict, Any

import httpx

logger = logging.getLogger(__name__)


class ActionExecutor:
    """Handles the execution of specific rule actions."""

    def __init__(self, http_client: httpx.AsyncClient, sensor_service_url: str):
        self.http_client = http_client
        self.sensor_service_url = sensor_service_url

    async def execute(self, action_dict: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Dispatcher method to execute an action based on its type."""
        action_type = action_dict.get("action_type")
        action_payload = action_dict.get("action_payload", {})
        action_id = action_dict.get("action_id")

        logger.info(f"Executing action {action_id} of type {action_type}")
        try:
            if action_type == "CONTROL_DEVICE":
                return await self._execute_device_control(action_payload)
            elif action_type == "SEND_NOTIFICATION":
                return await self._execute_email_notification(action_payload)
            elif action_type == "LOG_EVENT":
                return await self._execute_log_message(action_payload)
            else:
                logger.warning(f"Unknown action type: {action_type}")
                return False
        except Exception as e:
            logger.error(f"Error executing action {action_id}: {e}")
            return False

    async def _send_post_request(self, url: str, payload: Dict[str, Any], action_name: str) -> bool:
        """Generic helper for sending POST requests."""
        logger.info(f"{action_name} request to {url}: {payload}")
        try:
            response = await self.http_client.post(url, json=payload, timeout=5.0)
            response.raise_for_status()
            logger.info(f"✅ {action_name} successful: {response.status_code}")
            return True
        except httpx.RequestError as e:
            logger.error(f"❌ HTTP request failed for {action_name}: {e}")
            return False
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP error for {action_name}: {e.response.status_code} - {e.response.text}")
            return False

    async def _execute_device_control(self, payload: Dict[str, Any]) -> bool:
        """Executes the device control action."""
        url = f"{self.sensor_service_url}/actuator-mode-update"
        devices = payload.get("devices_to_control", [])
        control_payload = {"actuators_to_control": devices}
        return await self._send_post_request(url, control_payload, "Device control")

    async def _execute_email_notification(self, payload: Dict[str, Any]) -> bool:
        """Executes the email notification action."""
        to_email = payload.get("to")
        subject = payload.get("subject", "Rule Alert")
        logger.info(f"📧 Email notification: To={to_email}, Subject={subject}")
        # TODO: Implement actual email sending logic here
        return True

    async def _execute_log_message(self, payload: Dict[str, Any]) -> bool:
        """Executes the log message action."""
        message = payload.get("message", "Rule triggered")
        level = payload.get("level", "INFO").upper()
        log_func = getattr(logger, level.lower(), logger.info)
        log_func(message)
        return True