import json

import pytest

from common.models.rule_enums import RuleActionType
from rule_worker.services.action_executor import ActionExecutor

pytestmark = pytest.mark.asyncio


async def test_execute_unknown_action(mock_redis_service):
    executor = ActionExecutor(mock_redis_service)
    result = await executor.execute({"action_type": "UNKNOWN"})
    assert result is False


async def test_execute_device_control(mock_redis_service):
    executor = ActionExecutor(mock_redis_service)
    payload = {"actuators_to_control": [{"actuator_id": "pump_1", "command": "ON"}]}

    result = await executor.execute(
        {"action_type": RuleActionType.CONTROL_DEVICE.value, "action_payload": payload}
    )

    assert result is True
    mock_redis_service.publish.assert_called_once_with(
        "actuator_commands", json.dumps(payload)
    )


async def test_execute_device_control_no_actuators(mock_redis_service):
    executor = ActionExecutor(mock_redis_service)
    result = await executor.execute(
        {"action_type": RuleActionType.CONTROL_DEVICE.value, "action_payload": {}}
    )

    assert result is False
    mock_redis_service.publish.assert_not_called()


async def test_execute_log_event(mock_redis_service):
    executor = ActionExecutor(mock_redis_service)
    payload = {"message": "Test log", "level": "WARNING"}

    result = await executor.execute(
        {"action_type": RuleActionType.LOG_EVENT.value, "action_payload": payload}
    )

    assert result is True


async def test_execute_notification(mock_redis_service):
    executor = ActionExecutor(mock_redis_service)
    result = await executor.execute(
        {
            "action_type": RuleActionType.SEND_NOTIFICATION.value,
            "action_payload": {"msg": "hello"},
        }
    )

    assert result is True
