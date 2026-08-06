from unittest.mock import AsyncMock, patch

import pytest

from rule_worker.services.redis_service import RedisService

pytestmark = pytest.mark.asyncio


async def test_redis_connect():
    service = RedisService("localhost", 6379, 0)

    with patch("redis.asyncio.Redis", return_value=AsyncMock()) as mock_redis:
        mock_client = mock_redis.return_value
        mock_client.ping = AsyncMock(return_value=True)

        await service.connect()

        assert service.is_connected()
        mock_client.ping.assert_called_once()


async def test_redis_disconnect():
    service = RedisService("localhost", 6379, 0)
    service.client = AsyncMock()

    await service.disconnect()

    assert not service.is_connected()
    assert service.client is None


async def test_redis_get():
    service = RedisService("localhost", 6379, 0)
    service.client = AsyncMock()
    service.client.get.return_value = "10.5"

    val = await service.get("temp")
    assert val == "10.5"
    service.client.get.assert_called_once_with("sensor:temp")


async def test_redis_get_json():
    service = RedisService("localhost", 6379, 0)

    with patch.object(service, "get", AsyncMock(return_value='{"value": 15}')):
        val = await service.get_json("temp")
        assert val == {"value": 15}


async def test_redis_get_json_invalid():
    service = RedisService("localhost", 6379, 0)

    with patch.object(service, "get", AsyncMock(return_value="not_json")):
        val = await service.get_json("temp")
        assert val == "not_json"


async def test_redis_publish():
    service = RedisService("localhost", 6379, 0)
    service.client = AsyncMock()
    service.client.publish.return_value = 1

    res = await service.publish("ch1", "msg")
    assert res == 1


async def test_redis_ensure_consumer_group():
    service = RedisService("localhost", 6379, 0)
    service.client = AsyncMock()

    res = await service.ensure_consumer_group("s1", "g1")
    assert res is True
    service.client.xgroup_create.assert_called_once()


async def test_redis_read_stream():
    service = RedisService("localhost", 6379, 0)
    service.client = AsyncMock()
    service.client.xreadgroup.return_value = []

    res = await service.read_stream_group("s1", "g1", "c1")
    assert res == []


async def test_redis_ack_message():
    service = RedisService("localhost", 6379, 0)
    service.client = AsyncMock()

    res = await service.ack_message("s1", "g1", "m1")
    assert res is True
