from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rule_worker.services.evaluator import RuleEvaluator

pytestmark = pytest.mark.asyncio

async def test_is_rule_on_cooldown(sample_rule):
    from rule_worker.services.action_executor import ActionExecutor
    from rule_worker.services.context_builder import RuleContextBuilder
    from rule_worker.services.evaluator import RuleEvaluator
    evaluator = RuleEvaluator(MagicMock(spec=ActionExecutor), MagicMock(spec=RuleContextBuilder))
    
    assert evaluator._is_rule_on_cooldown(sample_rule) is False
    
    sample_rule.last_triggered_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    assert evaluator._is_rule_on_cooldown(sample_rule) is True
    
    sample_rule.last_triggered_at = datetime.now(timezone.utc) - timedelta(seconds=70)
    assert evaluator._is_rule_on_cooldown(sample_rule) is False

async def test_evaluate_single_rule_match(sample_rule, mock_db_session, mock_action_executor, context_builder):
    evaluator = RuleEvaluator(mock_action_executor, context_builder)
    
    # context_builder is not mocked, it uses mock_redis_service which returns 15 for sensor_1
    result = await evaluator.evaluate_single_rule(sample_rule, mock_db_session)
    
    assert result is True
    mock_action_executor.execute.assert_called_once()
    mock_db_session.execute.assert_called_once()
    mock_db_session.commit.assert_called_once()
    assert sample_rule.last_triggered_at is not None

async def test_evaluate_single_rule_no_match(sample_rule, mock_db_session, mock_action_executor, context_builder):
    evaluator = RuleEvaluator(mock_action_executor, context_builder)
    
    # Mock context to return low value
    with patch.object(context_builder, 'build', return_value={"value": 5, "sensor_id": "sensor_1"}):
        result = await evaluator.evaluate_single_rule(sample_rule, mock_db_session)
        
    assert result is False
    mock_action_executor.execute.assert_not_called()

async def test_evaluate_all_rules(sample_rule, mock_db_session, mock_action_executor, context_builder):
    evaluator = RuleEvaluator(mock_action_executor, context_builder)
    
    with patch('rule_worker.services.evaluator.rule_cache') as mock_cache:
        mock_cache.get_all_rules = AsyncMock(return_value=[sample_rule])
        await evaluator.evaluate_all_rules(mock_db_session)
        
    mock_action_executor.execute.assert_called_once()

async def test_evaluate_rules_for_sensor(sample_rule, mock_db_session, mock_action_executor, context_builder):
    evaluator = RuleEvaluator(mock_action_executor, context_builder)
    
    with patch('rule_worker.services.evaluator.rule_cache') as mock_cache:
        mock_cache.get_rules_for_sensor = AsyncMock(return_value=[sample_rule])
        await evaluator.evaluate_rules_for_sensor("sensor_1", 20.0, mock_db_session)
        
    mock_action_executor.execute.assert_called_once()
