from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sensor_data_service.services.Influxdb_service import InfluxDBService

pytestmark = pytest.mark.asyncio

@pytest.fixture
def influx_service():
    return InfluxDBService(
        url="http://mock:8086",
        token="mock_token",
        org="mock_org",
        bucket="mock_bucket"
    )

async def test_influx_service_aenter_aexit(influx_service):
    with patch("sensor_data_service.services.Influxdb_service.InfluxDBClientAsync") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client
        
        async with influx_service as service:
            assert service._client == mock_client
            assert service.write_api is not None
            assert service.query_api is not None
        
        mock_client.close.assert_called_once()
        assert influx_service._client is None

async def test_influx_service_save_sensor_data(influx_service):
    influx_service.write_api = AsyncMock()
    
    sensor_data = [
        {"sensor_id": "sensor_1", "sensor_type": "temp", "value": 25.5},
        {"invalid": "data"},
        {"sensor_id": "sensor_2", "sensor_type": "hum", "value": "invalid_value"}
    ]
    
    await influx_service.save_sensor_data(sensor_data)
    influx_service.write_api.write.assert_called_once()
    
    # Not initialized
    influx_service.write_api = None
    await influx_service.save_sensor_data(sensor_data) # Should just log and return

async def test_influx_service_query_data_by_sensor_id(influx_service):
    influx_service.query_api = AsyncMock()
    
    mock_result = MagicMock()
    mock_record = MagicMock()
    mock_record.get_time.return_value = datetime.now(timezone.utc)
    mock_record.get_value.return_value = 25.5
    mock_record.values = {"sensor_id": "sensor_1", "sensor_type": "temp"}
    
    mock_table = MagicMock()
    mock_table.records = [mock_record]
    mock_result.__iter__.return_value = [mock_table]
    
    influx_service.query_api.query.return_value = mock_result
    
    result = await influx_service.query_data_by_sensor_id("sensor_1", "1h")
    assert len(result) == 1
    assert result[0]["value"] == 25.5
    assert result[0]["sensor_id"] == "sensor_1"

async def test_influx_service_query_data_invalid_time(influx_service):
    influx_service.query_api = AsyncMock()
    with pytest.raises(ValueError):
        await influx_service.query_data_by_sensor_id("sensor_1", "invalid_time")

async def test_influx_service_ping(influx_service):
    influx_service.query_api = AsyncMock()
    
    assert await influx_service.ping() is True
    
    influx_service.query_api.query.side_effect = Exception("Ping failed")
    assert await influx_service.ping() is False
    
    influx_service.query_api = None
    assert await influx_service.ping() is False
