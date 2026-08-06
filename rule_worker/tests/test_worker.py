import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rule_worker.worker import (
    run_cache_reloader,
    run_periodic_evaluation,
    run_rule_worker_daemon,
)

pytestmark = pytest.mark.asyncio


async def test_run_cache_reloader():
    with patch("rule_worker.worker.rule_cache") as mock_cache:
        mock_cache.reload_rules = AsyncMock(
            side_effect=[None, asyncio.CancelledError()]
        )

        try:
            await run_cache_reloader(1)
        except asyncio.CancelledError:
            pass

        mock_cache.reload_rules.assert_called()


async def test_run_periodic_evaluation():
    evaluator = AsyncMock()

    mock_db = MagicMock()
    mock_session = AsyncMock()
    mock_db.__aenter__.return_value = mock_session

    with patch("rule_worker.worker.get_db", return_value=mock_db):
        evaluator.evaluate_all_rules.side_effect = [None, asyncio.CancelledError()]
        try:
            await run_periodic_evaluation(evaluator, 1)
        except asyncio.CancelledError:
            pass

        evaluator.evaluate_all_rules.assert_called()


async def test_run_rule_worker_daemon():
    with patch("rule_worker.worker.RedisService") as MockRedis:
        mock_redis = AsyncMock()
        MockRedis.return_value = mock_redis

        with patch("rule_worker.worker.httpx.AsyncClient") as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value = mock_client

            with (
                patch("rule_worker.worker.ActionExecutor") as mock_action,
                patch("rule_worker.worker.RuleContextBuilder") as mock_builder,
                patch("rule_worker.worker.RuleEvaluator") as mock_evaluator,
                patch("rule_worker.worker.StreamConsumer") as mock_stream,
                patch(
                    "rule_worker.worker.rule_cache.reload_rules", new_callable=AsyncMock
                ) as mock_reload,
                patch("asyncio.gather", side_effect=asyncio.CancelledError()),
            ):
                mock_stream.return_value.listen_for_sensor_updates = AsyncMock()

                try:
                    await run_rule_worker_daemon(1)
                except asyncio.CancelledError:
                    pass

                mock_redis.connect.assert_called_once()
                mock_reload.assert_called_once()
                mock_client.aclose.assert_called_once()
                mock_redis.disconnect.assert_called_once()
