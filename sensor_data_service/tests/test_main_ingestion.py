import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from sensor_data_service.main_ingestion import actuator_command_subscriber

pytestmark = pytest.mark.asyncio

async def test_actuator_command_subscriber_no_client():
    redis_service = AsyncMock()
    redis_service.client = None
    mqtt_service = AsyncMock()
    
    await actuator_command_subscriber(redis_service, mqtt_service)
    redis_service.update_desired_state.assert_not_called()

async def test_actuator_command_subscriber():
    redis_service = AsyncMock()
    redis_service.client = MagicMock()
    mqtt_service = AsyncMock()
    mqtt_service.client = AsyncMock()
    
    mock_pubsub = AsyncMock()
    redis_service.client.pubsub.return_value = mock_pubsub
    
    async def mock_listen():
        yield {
            "type": "message",
            "data": json.dumps({
                "actuators_to_control": [
                    {"device_id": "dev1", "actuator_id": "act1", "state": "on"},
                    {"actuator_id": "act2"} # missing device_id
                ]
            })
        }
        raise asyncio.CancelledError()
        
    mock_pubsub.listen = mock_listen
    
    await actuator_command_subscriber(redis_service, mqtt_service)
    
    mock_pubsub.subscribe.assert_called_once_with("actuator_commands")
    redis_service.update_desired_state.assert_called_once_with("dev1", {"act1": {"device_id": "dev1", "actuator_id": "act1", "state": "on"}})
    mqtt_service.client.publish.assert_called_once()
