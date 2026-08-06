from unittest.mock import AsyncMock, MagicMock, patch

import orjson
import pytest

from sensor_data_service.services.redis_service import RedisService

pytestmark = pytest.mark.asyncio


@pytest.fixture
def redis_service():
    return RedisService(host="mock_host", port=6379, db=0)


async def test_redis_connect_success(redis_service):
    with patch(
        "sensor_data_service.services.redis_service.redis_client.Redis"
    ) as mock_redis_cls:
        mock_client = AsyncMock()
        mock_redis_cls.return_value = mock_client

        await redis_service.connect()
        mock_client.ping.assert_called_once()
        assert redis_service.is_connected() is True


async def test_redis_disconnect(redis_service):
    redis_service.client = AsyncMock()
    await redis_service.disconnect()
    assert redis_service.is_connected() is False


async def test_redis_set_get_sensor_value(redis_service):
    redis_service.client = AsyncMock()
    redis_service.client.get.return_value = "25.5"

    await redis_service.set_new_sensors_value("temp_1", 25.5)
    redis_service.client.set.assert_called_with("sensor:temp_1", "25.5")

    val = await redis_service.get_sensor_value("temp_1")
    assert val == "25.5"
    redis_service.client.get.assert_called_with("sensor:temp_1")


async def test_redis_get_cached_history(redis_service):
    redis_service.client = AsyncMock()

    mock_data = [{"time": "2023", "value": 10}]
    redis_service.client.get.return_value = orjson.dumps(mock_data).decode("utf-8")

    result = await redis_service.get_cached_history("sensor_1", "1h")
    assert result == mock_data

    redis_service.client.get.return_value = None
    assert await redis_service.get_cached_history("sensor_1", "1h") is None


async def test_redis_set_cached_history(redis_service):
    redis_service.client = AsyncMock()
    mock_data = [{"time": "2023", "value": 10}]

    await redis_service.set_cached_history("sensor_1", "1h", mock_data)
    redis_service.client.setex.assert_called_once()


async def test_redis_update_cache_from_batch(redis_service):
    redis_service.client = MagicMock()

    mock_pipeline = AsyncMock()
    redis_service.client.pipeline.return_value = mock_pipeline
    mock_pipeline.__aenter__.return_value = mock_pipeline

    data = [{"sensor_id": "sensor_1", "value": 25.5}]
    await redis_service.update_cache_from_batch(data)

    mock_pipeline.set.assert_called_with("sensor:sensor_1", "25.5")
    mock_pipeline.xadd.assert_called_once()
    mock_pipeline.execute.assert_called_once()


async def test_redis_device_twin(redis_service):
    redis_service.client = AsyncMock()

    redis_service.client.get.return_value = None
    twin = await redis_service.get_device_twin("device_1")
    assert twin == {"desired": {}, "reported": {}}

    redis_service.client.get.return_value = orjson.dumps(
        {"desired": {"temp": 20}, "reported": {}}
    ).decode("utf-8")
    twin = await redis_service.get_device_twin("device_1")
    assert twin["desired"]["temp"] == 20

    await redis_service.update_desired_state("device_1", {"temp": 22})
    redis_service.client.set.assert_called_once()

    await redis_service.update_reported_state("device_1", {"temp": 21})
    assert redis_service.client.set.call_count == 2
