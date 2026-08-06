from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from common.models.rule_models import RuleTriggerType
from rule_worker.services.rule_cache import RuleCache

pytestmark = pytest.mark.asyncio


async def test_rule_cache_reload(sample_rule, sample_time_rule):
    cache = RuleCache()

    mock_db = MagicMock()
    mock_session = AsyncMock()
    mock_db.__aenter__.return_value = mock_session

    mock_result = MagicMock()
    mock_result.scalars().unique().all.return_value = [sample_rule, sample_time_rule]
    mock_session.execute.return_value = mock_result

    with patch("rule_worker.services.rule_cache.get_db", return_value=mock_db):
        await cache.reload_rules()

    sensor_rules = await cache.get_rules_for_sensor("sensor_1")
    assert len(sensor_rules) == 1
    assert sensor_rules[0].rule_id == "test_rule_1"

    time_rules = await cache.get_time_rules()
    assert len(time_rules) == 1
    assert time_rules[0].rule_id == "test_rule_2"

    all_rules = await cache.get_all_rules()
    assert len(all_rules) == 2

    sensor_filtered = await cache.get_all_rules(RuleTriggerType.SENSOR_THRESHOLD)
    assert len(sensor_filtered) == 1
