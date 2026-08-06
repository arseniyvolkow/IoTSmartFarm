import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_health_check(async_client: AsyncClient):
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert data["mqtt_status"] == "connected"
    assert data["influxdb_status"] == "connected"
    assert data["redis_status"] == "connected"


async def test_simulate_sensor_data(
    async_client: AsyncClient, mock_influx_service, mock_redis_service
):
    payload = {
        "sensors": [
            {"sensor_id": "temp_kitchen", "sensor_type": "temperature", "value": 25.5},
            {"sensor_id": "hum_kitchen", "sensor_type": "humidity", "value": 60.0},
        ]
    }
    response = await async_client.post("/simulate-sensor-data", json=payload)
    assert response.status_code == 201
    assert response.json()["status"] == "success"

    mock_influx_service.save_sensor_data.assert_called_once()
    mock_redis_service.update_cache_from_batch.assert_called_once()


async def test_get_sensor_value_found(async_client: AsyncClient, mock_redis_service):
    mock_redis_service.get_sensor_value.return_value = 25.5
    response = await async_client.get("/sensor-value/temp_kitchen")
    assert response.status_code == 200
    assert response.json()["value"] == 25.5


async def test_get_sensor_value_not_found(
    async_client: AsyncClient, mock_redis_service
):
    mock_redis_service.get_sensor_value.return_value = None
    response = await async_client.get("/sensor-value/unknown_sensor")
    assert response.status_code == 404


async def test_get_timeseries_data_by_id_cached(
    async_client: AsyncClient, mock_redis_service
):
    mock_redis_service.get_cached_history.return_value = [
        {"time": "2023-01-01T00:00:00Z", "value": 25.5}
    ]
    response = await async_client.get("/sensor-data/temp_kitchen/1h")
    assert response.status_code == 200
    assert response.json()["cached"] is True
    assert len(response.json()["data"]) == 1


async def test_get_timeseries_data_by_id_not_cached(
    async_client: AsyncClient, mock_redis_service, mock_influx_service
):
    mock_redis_service.get_cached_history.return_value = None
    mock_influx_service.query_data_by_sensor_id.return_value = [
        {"time": "2023-01-01T00:00:00Z", "value": 25.5}
    ]

    response = await async_client.get("/sensor-data/temp_kitchen/1h")
    assert response.status_code == 200
    assert response.json()["cached"] is False
    assert len(response.json()["data"]) == 1

    mock_influx_service.query_data_by_sensor_id.assert_called_once_with(
        sensor_id="temp_kitchen", time_range="1h"
    )
    mock_redis_service.set_cached_history.assert_called_once()


async def test_actuator_mode_update(async_client: AsyncClient, mock_mqtt_service):
    payload = {"actuators_to_control": [{"actuator_id": "valve_1", "command": "ON"}]}
    response = await async_client.post("/actuator-mode-update", json=payload)
    assert response.status_code == 202
    mock_mqtt_service.publish_mqtt_message.assert_called_once_with(
        "actuator/valve_1/command", "ON"
    )
