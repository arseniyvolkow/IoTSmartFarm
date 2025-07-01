import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch
from httpx import AsyncClient
import json
import os
from .main import app
from .database import Settings, InfluxDBService, MQTTService
from faker import Faker

fake = Faker()


@pytest_asyncio.fixture
async def client():
    """Create test client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    return Settings()


@pytest.fixture
def sample_sensor_data():
    """Sample sensor data for testing."""
    return {
        "sensors": [
            {
                "sensor_id": "temp_001",
                "sensor_type": "temperature",
                "value": 25.5
            },
            {
                "sensor_id": "hum_001",
                "sensor_type": "humidity",
                "value": 60.0
            }
        ]
    }


@pytest.fixture
def sample_mqtt_message_data():
    """Sample MQTT message data for testing."""
    return {
        "topic": "device/test-device-001/data",
        "payload": json.dumps({
            "sensors": {
                "temperature": 23.5,
                "humidity": 65.0,
                "soil_moisture": 45.0
            }
        })
    }


@pytest.fixture
def mock_influxdb_client():
    """Mock InfluxDB client for testing."""
    mock_client = Mock()
    mock_client.ping.return_value = True
    mock_client.query_api.return_value.query.return_value = []
    return mock_client


@pytest.fixture
def mock_mqtt_client():
    """Mock MQTT client for testing."""
    mock_client = Mock()
    mock_client.is_connected.return_value = True
    mock_client.connect.return_value = 0
    mock_client.subscribe.return_value = (0, 1)
    mock_client.loop_start.return_value = None
    mock_client.loop_stop.return_value = None
    return mock_client


@pytest.fixture
def invalid_sensor_data_samples():
    """Invalid sensor data samples for testing."""
    return [
        {},  # Empty
        {"sensors": {}},  # Empty sensors
        {"invalid_key": "value"},  # Missing sensors key
        {"sensors": [{"sensor_id": "temp_001"}]},  # Missing required fields
        {"sensors": [{"sensor_type": "temperature", "value": "invalid"}]},  # Invalid value type
    ]


@pytest.fixture
def valid_time_parameters():
    """Valid time parameters for testing."""
    return ["1h", "24h", "7d", "30d"]


@pytest.fixture
def invalid_time_parameters():
    """Invalid time parameters for testing."""
    return ["1m", "2h", "3days", "invalid", ""]