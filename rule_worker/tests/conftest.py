from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.rule_enums import RuleActionType
from common.models.rule_models import RuleActions, Rules, RuleTriggerType
from rule_worker.services.action_executor import ActionExecutor
from rule_worker.services.context_builder import RuleContextBuilder
from rule_worker.services.redis_service import RedisService


@pytest.fixture
def mock_db_session():
    return AsyncMock(spec=AsyncSession)

@pytest.fixture
def mock_redis_service():
    service = AsyncMock(spec=RedisService)
    service.publish = AsyncMock(return_value=1)
    service.get_json = AsyncMock(return_value={"value": 15})
    service.get = AsyncMock(return_value="15")
    return service

@pytest.fixture
def mock_action_executor(mock_redis_service):
    executor = ActionExecutor(mock_redis_service)
    executor.execute = AsyncMock(return_value=True)
    return executor

@pytest.fixture
def context_builder(mock_redis_service):
    return RuleContextBuilder(mock_redis_service)

@pytest.fixture
def sample_rule():
    rule = Rules(
        rule_id="test_rule_1",
        rule_name="Test Rule",
        is_active=True,
        trigger_type=RuleTriggerType.SENSOR_THRESHOLD,
        sensor_id="sensor_1",
        rule_expression="value > 10",
        cooldown_seconds=60,
        last_triggered_at=None
    )
    action = RuleActions(
        action_id="action_1",
        rule_id="test_rule_1",
        action_type=RuleActionType.LOG_EVENT,
        action_payload={"message": "High value detected"},
        execution_order=1
    )
    rule.actions = [action]
    return rule

@pytest.fixture
def sample_time_rule():
    rule = Rules(
        rule_id="test_rule_2",
        rule_name="Time Rule",
        is_active=True,
        trigger_type=RuleTriggerType.TIME_BASED,
        sensor_id=None,
        rule_expression="hour == 8",
        cooldown_seconds=60,
        last_triggered_at=None
    )
    rule.actions = []
    return rule
