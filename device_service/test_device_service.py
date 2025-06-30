import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from .services.device_service import DeviceService
from .models import Devices, Sensors, Farms
from .schemas import AddNewDevice, SensorInfo
from faker import Faker

fake = Faker()


class TestDeviceService:
    """Unit tests for DeviceService class."""

    @pytest_asyncio.fixture
    async def mock_db_session(self):
        """Mock database session."""
        session = Mock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.add = Mock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.bulk_save_objects = Mock()
        return session

    @pytest_asyncio.fixture
    async def device_service(self, mock_db_session):
        """Create DeviceService instance with mock session."""
        return DeviceService(mock_db_session)

    @pytest_asyncio.fixture
    def sample_device(self):
        """Create a sample device for testing."""
        device = Devices(
            unique_device_id="test-device-001",
            user_id="user-123",
            device_ip_address="192.168.1.100",
            model_number="TEST-001",
            firmware_version="1.0.0",
            status="active"
        )
        device.sensors = []
        return device

    @pytest_asyncio.fixture
    def sample_add_device_data(self):
        """Sample data for adding a new device."""
        return AddNewDevice(
            username="testuser",
            password="TestPass123!",
            unique_device_id="test-device-002",
            device_ip_address="192.168.1.101",
            model_number="TEST-002",
            firmware_version="1.1.0",
            sensors_list=[
                SensorInfo(
                    sensor_type="temperature",
                    units_of_measure="celsius",
                    max_value=50.0,
                    min_value=-10.0
                ),
                SensorInfo(
                    sensor_type="humidity",
                    units_of_measure="percentage",
                    max_value=100.0,
                    min_value=0.0
                )
            ]
        )

    @pytest_asyncio.async def test_get_device_success(self, device_service, sample_device):
        """Test successful device retrieval."""
        # Mock the database query result
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_device
        device_service.db.execute.return_value = mock_result

        result = await device_service.get("test-device-001")

        assert result == sample_device
        device_service.db.execute.assert_called_once()

    @pytest_asyncio.async def test_get_device_not_found(self, device_service):
        """Test device not found scenario."""
        # Mock empty query result
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        device_service.db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await device_service.get("non-existent-device")

        assert exc_info.value.status_code == 404
        assert "Device not found" in str(exc_info.value.detail)

    @pytest_asyncio.async def test_create_device_success(self, device_service, sample_add_device_data):
        """Test successful device creation."""
        # Mock that device doesn't exist
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        device_service.db.execute.return_value = mock_result

        result = await device_service.create("user-123", sample_add_device_data)

        assert result.unique_device_id == sample_add_device_data.unique_device_id
        assert result.user_id == "user-123"
        assert result.status == "inactive"
        device_service.db.add.assert_called_once()
        device_service.db.flush.assert_called_once()
        device_service.db.bulk_save_objects.assert_called_once()
        device_service.db.commit.assert_called_once()

    @pytest_asyncio.async def test_create_device_already_exists(self, device_service, sample_add_device_data, sample_device):
        """Test device creation when device already exists."""
        # Mock that device already exists
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_device
        device_service.db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await device_service.create("user-123", sample_add_device_data)

        assert exc_info.value.status_code == 400
        assert "Device already exists" in str(exc_info.value.detail)

    @pytest_asyncio.async def test_get_unassigned_devices(self, device_service):
        """Test getting unassigned devices with pagination."""
        # Mock cursor_paginate method
        device_service.cursor_paginate = AsyncMock(return_value=([], None))

        result = await device_service.get_unassigned_devices(
            user_id="user-123",
            sort_column="created_at",
            cursor=None,
            limit=10
        )

        items, next_cursor = result
        assert items == []
        assert next_cursor is None
        device_service.cursor_paginate.assert_called_once()

    @pytest_asyncio.async def test_assign_device_to_farm(self, device_service, sample_device):
        """Test assigning device to farm."""
        farm = Farms(
            farm_id="farm-123",
            farm_name="Test Farm",
            total_area=100,
            user_id="user-123",
            location="Test Location",
            crop_id="crop-123"
        )

        result = await device_service.assign_device_to_farm(sample_device, farm)

        assert result.farm_id == "farm-123"
        device_service.db.commit.assert_called_once()


class TestDeviceRoutes:
    """Integration tests for device routes."""

    @pytest_asyncio.async def test_health_check(self, client):
        """Test health check endpoint."""
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"health": "ok"}

    @pytest_asyncio.async def test_create_device_unauthorized(self, client, sample_device_data):
        """Test device creation without proper authentication."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 401
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response

            response = await client.post("/devices/device", json=sample_device_data)
            assert response.status_code == 401

    @pytest_asyncio.async def test_create_device_success(self, client, sample_device_data, test_db):
        """Test successful device creation."""
        with patch('httpx.AsyncClient') as mock_client:
            # Mock successful user service response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"user_id": "user-123"}
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response

            response = await client.post("/devices/device", json=sample_device_data)
            assert response.status_code == 201
            data = response.json()
            assert data["status"] == "success"
            assert "device_id" in data

    @pytest_asyncio.async def test_get_unassigned_devices_unauthorized(self, client):
        """Test get unassigned devices without authentication."""
        response = await client.get("/devices/unassigned-devices?sort_column=created_at")
        assert response.status_code == 401

    @pytest_asyncio.async def test_update_device_unauthorized(self, client):
        """Test device update without authentication."""
        response = await client.patch(
            "/devices/device/test-device-001?new_status=active"
        )
        assert response.status_code == 401

    @pytest_asyncio.async def test_delete_device_unauthorized(self, client):
        """Test device deletion without authentication."""
        response = await client.delete("/devices/device/test-device-001")
        assert response.status_code == 401


class TestDeviceModels:
    """Tests for device models and schemas."""

    def test_sensor_info_validation(self):
        """Test SensorInfo schema validation."""
        sensor_data = {
            "sensor_type": "temperature",
            "units_of_measure": "celsius",
            "max_value": 50.0,
            "min_value": -10.0
        }
        sensor = SensorInfo(**sensor_data)
        assert sensor.sensor_type == "temperature"
        assert sensor.max_value == 50.0
        assert sensor.min_value == -10.0

    def test_add_new_device_validation(self):
        """Test AddNewDevice schema validation."""
        device_data = {
            "username": "testuser",
            "password": "TestPass123!",
            "unique_device_id": "test-device-001",
            "device_ip_address": "192.168.1.100",
            "model_number": "TEST-001",
            "firmware_version": "1.0.0",
            "sensors_list": [
                {
                    "sensor_type": "temperature",
                    "units_of_measure": "celsius",
                    "max_value": 50.0,
                    "min_value": -10.0
                }
            ]
        }
        device = AddNewDevice(**device_data)
        assert device.unique_device_id == "test-device-001"
        assert len(device.sensors_list) == 1
        assert device.sensors_list[0].sensor_type == "temperature"

    def test_device_model_creation(self):
        """Test Device model creation."""
        device = Devices(
            unique_device_id="test-device-001",
            user_id="user-123",
            device_ip_address="192.168.1.100",
            model_number="TEST-001",
            firmware_version="1.0.0",
            status="active"
        )
        assert device.unique_device_id == "test-device-001"
        assert device.user_id == "user-123"
        assert device.status.value == "active"  # Enum value