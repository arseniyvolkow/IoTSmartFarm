import pytest

from common.models.rule_models import Rules, RuleTriggerType
from rule_worker.services.context_builder import RuleContextBuilder

pytestmark = pytest.mark.asyncio


async def test_build_context_sensor(sample_rule, mock_redis_service):
    builder = RuleContextBuilder(mock_redis_service)
    context = await builder.build(sample_rule)

    assert context is not None
    assert context["sensor_id"] == "sensor_1"
    assert context["value"] == 15.0


async def test_build_context_sensor_triggered_value(sample_rule, mock_redis_service):
    builder = RuleContextBuilder(mock_redis_service)
    context = await builder.build(sample_rule, triggered_value=25.5)

    assert context is not None
    assert context["sensor_id"] == "sensor_1"
    assert context["value"] == 25.5
    mock_redis_service.get_json.assert_not_called()


async def test_build_context_sensor_no_id():
    rule = Rules(
        rule_id="r1",
        rule_name="r1",
        trigger_type=RuleTriggerType.SENSOR_THRESHOLD,
        sensor_id=None,
    )
    builder = RuleContextBuilder(None)
    context = await builder.build(rule)
    assert context is None


async def test_build_context_time(sample_time_rule):
    builder = RuleContextBuilder(None)
    context = await builder.build(sample_time_rule)

    assert context is not None
    assert "hour" in context
    assert "minute" in context
    assert "day_of_week" in context
