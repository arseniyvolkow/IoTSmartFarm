from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sensor_data_service.services.mqtt_service import AsyncMQTTService

pytestmark = pytest.mark.asyncio


@pytest.fixture
def influx_mock():
    return AsyncMock()


@pytest.fixture
def redis_mock():
    return AsyncMock()


@pytest.fixture
def mqtt_service(influx_mock, redis_mock):
    return AsyncMQTTService(
        broker="mock_broker",
        port=1883,
        username="mock_user",
        password="mock_password",
        influx_service=influx_mock,
        redis_service=redis_mock,
        client_id="test_client",
    )


async def test_mqtt_service_start_stop(mqtt_service):
    await mqtt_service.start(mode="api")
    assert mqtt_service._running is True
    assert len(mqtt_service._tasks) > 0

    await mqtt_service.stop()
    assert mqtt_service._running is False
    assert len(mqtt_service._tasks) == 0


async def test_mqtt_service_publish_message(mqtt_service):
    await mqtt_service.start(mode="api")

    res = await mqtt_service.publish_mqtt_message("test/topic", {"key": "value"})
    assert res == {"status": "queued"}

    assert mqtt_service._publish_queue.qsize() == 1

    await mqtt_service.stop()


async def test_mqtt_service_is_connected(mqtt_service):
    assert mqtt_service.is_connected() is False
    mqtt_service._connected = True
    assert mqtt_service.is_connected() is True


async def test_mqtt_handle_twin_message_get(mqtt_service, redis_mock):
    redis_mock.get_device_twin.return_value = {"desired": {}, "reported": {}}

    mock_msg = MagicMock()
    mock_msg.topic.value = "device/device_1/twin/get"

    with patch.object(mqtt_service, "publish_mqtt_message", new_callable=AsyncMock):
        # Override publish to avoid queuing and test directly if we wanted,
        # but in code it uses `await self.publish(reply_topic, ...)`
        # wait, the code calls `self.publish`, let's see if that exists.
        # Oh, in the code it's `self.publish(...)`. Let's mock it.
        mqtt_service.publish = AsyncMock()
        await mqtt_service._handle_twin_message(mock_msg)
        redis_mock.get_device_twin.assert_called_with("device_1")
        mqtt_service.publish.assert_called_once()


async def test_mqtt_handle_twin_message_reported(mqtt_service, redis_mock):
    mock_msg = MagicMock()
    mock_msg.topic.value = "device/device_1/twin/reported"
    mock_msg.payload = b'{"temp": 20}'

    await mqtt_service._handle_twin_message(mock_msg)
    redis_mock.update_reported_state.assert_called_with("device_1", {"temp": 20})


async def test_mqtt_process_batch(mqtt_service, influx_mock, redis_mock):
    mock_msg = MagicMock()
    mock_msg.payload = b'{"sensors": [{"sensor_id": "s1", "value": 10}]}'

    await mqtt_service._process_batch([mock_msg])

    influx_mock.save_sensor_data.assert_called_once()
    redis_mock.update_cache_from_batch.assert_called_once()

    # Test dictionary format
    mock_msg2 = MagicMock()
    mock_msg2.payload = b'{"sensors": {"s2": 20, "s3": {"value": 30}}}'
    await mqtt_service._process_batch([mock_msg2])
    assert influx_mock.save_sensor_data.call_count == 2
    assert redis_mock.update_cache_from_batch.call_count == 2
