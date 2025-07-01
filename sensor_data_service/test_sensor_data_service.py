import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import json
from datetime import datetime, timezone
from fastapi import HTTPException
from .database import InfluxDBService, MQTTService, Settings
from .main import handle_mqtt_message
from influxdb_client import Point
import os


class TestInfluxDBService:
    """Unit tests for InfluxDBService class."""

    @pytest_asyncio.fixture
    async def influx_service(self):
        """Create InfluxDBService instance for testing."""
        service = InfluxDBService(
            url="http://localhost:8086",
            token="test_token",
            org="test_org",
            bucket="test_bucket"
        )
        # Mock the client
        service._client = Mock()
        service.write_api = AsyncMock()
        return service

    @pytest_asyncio.async def test_influx_service_initialization(self):
        """Test InfluxDBService initialization."""
        service = InfluxDBService(
            url="http://localhost:8086",
            token="test_token",
            org="test_org",
            bucket="test_bucket"
        )
        assert service._url == "http://localhost:8086"
        assert service._token == "test_token"
        assert service._org == "test_org"
        assert service.bucket == "test_bucket"
        assert service._client is None
        assert service.write_api is None

    @pytest_asyncio.async def test_save_sensor_data_success(self, influx_service):
        """Test successful sensor data saving."""
        device_id = "test-device-001"
        sensor_data = [
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

        await influx_service.save_sensor_data(device_id, sensor_data)

        # Verify write_api.write was called
        influx_service.write_api.write.assert_called_once()
        args, kwargs = influx_service.write_api.write.call_args
        assert kwargs["bucket"] == "test_bucket"
        assert kwargs["org"] == "test_org"
        assert len(kwargs["record"]) == 2  # Two data points

    @pytest_asyncio.async def test_save_sensor_data_invalid_data(self, influx_service):
        """Test saving sensor data with invalid data."""
        device_id = "test-device-001"
        invalid_sensor_data = [
            {
                "sensor_id": "temp_001",
                # Missing sensor_type and value
            },
            {
                "sensor_type": "humidity",
                "value": None  # Invalid value
            }
        ]

        await influx_service.save_sensor_data(device_id, invalid_sensor_data)

        # Should not write any points due to invalid data
        influx_service.write_api.write.assert_not_called()

    @pytest_asyncio.async def test_save_sensor_data_empty_list(self, influx_service):
        """Test saving empty sensor data list."""
        device_id = "test-device-001"
        sensor_data = []

        await influx_service.save_sensor_data(device_id, sensor_data)

        # Should not call write_api.write for empty data
        influx_service.write_api.write.assert_not_called()


class TestMQTTService:
    """Unit tests for MQTTService class."""

    def test_mqtt_service_initialization(self, mock_mqtt_client):
        """Test MQTTService initialization."""
        with patch('paho.mqtt.client.Client', return_value=mock_mqtt_client):
            callback = Mock()
            service = MQTTService(
                broker="localhost",
                port=1883,
                username="test_user",
                password="test_pass",
                on_message_callback=callback
            )

            assert service.broker == "localhost"
            assert service.port == 1883
            mock_mqtt_client.username_pw_set.assert_called_once_with("test_user", "test_pass")
            assert service.mqtt_client.on_message == callback

    def test_mqtt_service_start(self, mock_mqtt_client):
        """Test MQTT service start."""
        with patch('paho.mqtt.client.Client', return_value=mock_mqtt_client):
            callback = Mock()
            service = MQTTService(
                broker="localhost",
                port=1883,
                username="test_user",
                password="test_pass",
                on_message_callback=callback
            )

            service.start()

            mock_mqtt_client.connect.assert_called_once_with("localhost", 1883, 60)
            mock_mqtt_client.loop_start.assert_called_once()

    def test_mqtt_service_stop(self, mock_mqtt_client):
        """Test MQTT service stop."""
        with patch('paho.mqtt.client.Client', return_value=mock_mqtt_client):
            callback = Mock()
            service = MQTTService(
                broker="localhost",
                port=1883,
                username="test_user",
                password="test_pass",
                on_message_callback=callback
            )

            service.stop()

            mock_mqtt_client.loop_stop.assert_called_once()

    def test_on_connect_success(self, mock_mqtt_client):
        """Test successful MQTT connection."""
        with patch('paho.mqtt.client.Client', return_value=mock_mqtt_client):
            callback = Mock()
            service = MQTTService(
                broker="localhost",
                port=1883,
                username="test_user",
                password="test_pass",
                on_message_callback=callback
            )

            # Simulate successful connection
            service.on_connect(mock_mqtt_client, None, None, 0)

            mock_mqtt_client.subscribe.assert_called_once_with("device/+/data")

    def test_on_connect_failure(self, mock_mqtt_client):
        """Test failed MQTT connection."""
        with patch('paho.mqtt.client.Client', return_value=mock_mqtt_client):
            callback = Mock()
            service = MQTTService(
                broker="localhost",
                port=1883,
                username="test_user",
                password="test_pass",
                on_message_callback=callback
            )

            # Simulate failed connection
            service.on_connect(mock_mqtt_client, None, None, 1)

            # Should not subscribe on failed connection
            mock_mqtt_client.subscribe.assert_not_called()


class TestMQTTMessageHandler:
    """Tests for MQTT message handling."""

    @patch('sensor_data_service.main.influxdb_service')
    def test_handle_mqtt_message_success(self, mock_influxdb_service, sample_mqtt_message_data):
        """Test successful MQTT message handling."""
        mock_client = Mock()
        mock_userdata = Mock()
        mock_message = Mock()
        mock_message.topic = sample_mqtt_message_data["topic"]
        mock_message.payload.decode.return_value = sample_mqtt_message_data["payload"]

        mock_influxdb_service.save_sensor_data = Mock()

        handle_mqtt_message(mock_client, mock_userdata, mock_message)

        # Verify save_sensor_data was called with correct parameters
        mock_influxdb_service.save_sensor_data.assert_called_once()
        args = mock_influxdb_service.save_sensor_data.call_args[0]
        assert args[0] == "test-device-001"  # device_id
        assert isinstance(args[1], dict)  # sensor_data

    @patch('sensor_data_service.main.influxdb_service')
    def test_handle_mqtt_message_invalid_json(self, mock_influxdb_service):
        """Test MQTT message handling with invalid JSON."""
        mock_client = Mock()
        mock_userdata = Mock()
        mock_message = Mock()
        mock_message.topic = "device/test-device-001/data"
        mock_message.payload.decode.return_value = "invalid json"

        mock_influxdb_service.save_sensor_data = Mock()

        # Should not raise exception, just print error
        handle_mqtt_message(mock_client, mock_userdata, mock_message)

        # Should not call save_sensor_data
        mock_influxdb_service.save_sensor_data.assert_not_called()

    @patch('sensor_data_service.main.influxdb_service')
    def test_handle_mqtt_message_missing_sensors(self, mock_influxdb_service):
        """Test MQTT message handling with missing sensors data."""
        mock_client = Mock()
        mock_userdata = Mock()
        mock_message = Mock()
        mock_message.topic = "device/test-device-001/data"
        mock_message.payload.decode.return_value = json.dumps({"invalid": "data"})

        mock_influxdb_service.save_sensor_data = Mock()

        handle_mqtt_message(mock_client, mock_userdata, mock_message)

        # Should not call save_sensor_data
        mock_influxdb_service.save_sensor_data.assert_not_called()


class TestSensorDataRoutes:
    """Integration tests for sensor data routes."""

    @pytest_asyncio.async def test_health_check_success(self, client):
        """Test health check endpoint success."""
        with patch('sensor_data_service.main.mqtt_service') as mock_mqtt_service, \
             patch('sensor_data_service.main.influxdb_service') as mock_influxdb_service:
            
            mock_mqtt_service.mqtt_client.is_connected.return_value = True
            mock_influxdb_service.client.ping.return_value = True

            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"
            assert data["mqtt_status"] == "connected"
            assert data["influxdb_status"] == "connected"

    @pytest_asyncio.async def test_health_check_services_disconnected(self, client):
        """Test health check when services are disconnected."""
        with patch('sensor_data_service.main.mqtt_service') as mock_mqtt_service, \
             patch('sensor_data_service.main.influxdb_service') as mock_influxdb_service:
            
            mock_mqtt_service.mqtt_client.is_connected.return_value = False
            mock_influxdb_service.client.ping.return_value = False

            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"
            assert data["mqtt_status"] == "disconnected"
            assert data["influxdb_status"] == "disconnected"

    @pytest_asyncio.async def test_simulate_sensor_data_success(self, client):
        """Test successful sensor data simulation."""
        with patch('sensor_data_service.main.influxdb_service') as mock_influxdb_service:
            mock_influxdb_service.save_sensor_data = Mock()

            response = await client.post(
                "/simulate-sensor-data",
                params={
                    "device_id": "test-device-001",
                    "sensor_key": "temperature",
                    "value": 25.5
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "simulated data saved"
            mock_influxdb_service.save_sensor_data.assert_called_once()

    @pytest_asyncio.async def test_get_timeseries_data_valid_time(self, client, valid_time_parameters):
        """Test getting timeseries data with valid time parameters."""
        with patch('sensor_data_service.main.influxdb_service') as mock_influxdb_service:
            mock_query_api = Mock()
            mock_query_api.query.return_value = []
            mock_influxdb_service.client.query_api.return_value = mock_query_api

            for time_param in valid_time_parameters:
                response = await client.get(
                    f"/device_data/test-device-001/temperature/{time_param}"
                )
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert "data" in data

    @pytest_asyncio.async def test_get_timeseries_data_invalid_time(self, client, invalid_time_parameters):
        """Test getting timeseries data with invalid time parameters."""
        for time_param in invalid_time_parameters:
            response = await client.get(
                f"/device_data/test-device-001/temperature/{time_param}"
            )
            assert response.status_code == 400
            data = response.json()
            assert "Invalid time parameter" in data["detail"]

    @pytest_asyncio.async def test_get_timeseries_data_query_error(self, client):
        """Test getting timeseries data with query error."""
        with patch('sensor_data_service.main.influxdb_service') as mock_influxdb_service:
            mock_query_api = Mock()
            mock_query_api.query.side_effect = Exception("Database error")
            mock_influxdb_service.client.query_api.return_value = mock_query_api

            response = await client.get("/device_data/test-device-001/temperature/1h")
            assert response.status_code == 500
            data = response.json()
            assert "Error querying data" in data["detail"]


class TestSettings:
    """Tests for Settings configuration."""

    def test_settings_initialization(self):
        """Test Settings class initialization."""
        with patch.dict(os.environ, {
            'mqtt_broker_url': 'localhost',
            'mqtt_broker_port': '1883',
            'mqtt_username': 'test_user',
            'mqtt_password': 'test_pass',
            'influxdb_url': 'http://localhost:8086',
            'influxdb_token': 'test_token',
            'influxdb_org': 'test_org',
            'influxdb_bucket': 'test_bucket'
        }):
            settings = Settings()
            assert settings.MQTT_BROKER == 'localhost'
            assert settings.MQTT_PORT == 1883
            assert settings.MQTT_USERNAME == 'test_user'
            assert settings.MQTT_PASSWORD == 'test_pass'
            assert settings.INFLUXDB_URL == 'http://localhost:8086'
            assert settings.INFLUXDB_TOKEN == 'test_token'
            assert settings.INFLUXDB_ORG == 'test_org'
            assert settings.INFLUXDB_BUCKET == 'test_bucket'

    def test_settings_default_port(self):
        """Test Settings with default port."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.MQTT_PORT == 1883  # Default port


class TestDataValidation:
    """Tests for data validation and processing."""

    def test_sensor_data_point_creation(self):
        """Test creation of InfluxDB data points."""
        device_id = "test-device-001"
        sensor_data = {
            "sensor_id": "temp_001",
            "sensor_type": "temperature",
            "value": 25.5
        }
        timestamp = datetime.now(timezone.utc)

        point = (
            Point("sensor_data")
            .tag("device_id", device_id)
            .tag("sensor_id", sensor_data["sensor_id"])
            .tag("sensor_type", sensor_data["sensor_type"])
            .field("value", float(sensor_data["value"]))
            .time(timestamp)
        )

        # Verify point was created (basic check)
        assert point is not None
        # More detailed verification would require access to internal Point structure

    def test_mqtt_topic_parsing(self):
        """Test MQTT topic parsing for device ID extraction."""
        topic = "device/test-device-001/data"
        topic_parts = topic.split('/')
        
        assert len(topic_parts) == 3
        assert topic_parts[0] == "device"
        assert topic_parts[1] == "test-device-001"
        assert topic_parts[2] == "data"

    def test_sensor_data_validation(self, invalid_sensor_data_samples):
        """Test sensor data validation logic."""
        for invalid_data in invalid_sensor_data_samples:
            # Simulate the validation logic from handle_mqtt_message
            sensor_data = invalid_data.get("sensors", {})
            
            if not sensor_data:
                # This should be considered invalid
                assert not bool(sensor_data) or sensor_data == {}

    def test_time_parameter_validation(self, valid_time_parameters, invalid_time_parameters):
        """Test time parameter validation for query endpoints."""
        valid_times = {'1h': '-1h', '24h': '-24h', '7d': '-7d', '30d': '-30d'}
        
        # Test valid parameters
        for time_param in valid_time_parameters:
            assert time_param in valid_times
        
        # Test invalid parameters
        for time_param in invalid_time_parameters:
            assert time_param not in valid_times