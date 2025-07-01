import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from .services.farm_service import FarmService
from .models import Farms
from .schemas import FarmModel
from faker import Faker

fake = Faker()


class TestFarmService:
    """Unit tests for FarmService class."""

    @pytest_asyncio.fixture
    async def mock_db_session(self):
        """Mock database session."""
        session = Mock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.add = Mock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        return session

    @pytest_asyncio.fixture
    async def farm_service(self, mock_db_session):
        """Create FarmService instance with mock session."""
        return FarmService(mock_db_session)

    @pytest_asyncio.fixture
    def sample_farm(self):
        """Create a sample farm for testing."""
        return Farms(
            farm_id="farm-123",
            farm_name="Test Farm",
            total_area=100,
            user_id="user-123",
            location="Test Location",
            crop_id="crop-123"
        )

    @pytest_asyncio.fixture
    def sample_farm_data(self):
        """Sample farm data for testing."""
        return FarmModel(
            farm_name="New Test Farm",
            total_area=150,
            location="New Location",
            crop="corn"
        )

    @pytest_asyncio.async def test_get_farm_success(self, farm_service, sample_farm):
        """Test successful farm retrieval."""
        # Mock the database query result
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_farm
        farm_service.db.execute.return_value = mock_result

        result = await farm_service.get("farm-123")

        assert result == sample_farm
        farm_service.db.execute.assert_called_once()

    @pytest_asyncio.async def test_get_farm_not_found(self, farm_service):
        """Test farm not found scenario."""
        # Mock empty query result
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        farm_service.db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await farm_service.get("non-existent-farm")

        assert exc_info.value.status_code == 404

    @pytest_asyncio.async def test_create_farm_success(self, farm_service, sample_farm_data):
        """Test successful farm creation."""
        user_id = "user-123"
        
        result = await farm_service.create(sample_farm_data, user_id)

        assert result.farm_name == sample_farm_data.farm_name
        assert result.user_id == user_id
        assert result.total_area == sample_farm_data.total_area
        farm_service.db.add.assert_called_once()
        farm_service.db.commit.assert_called_once()

    @pytest_asyncio.async def test_get_all_farms(self, farm_service):
        """Test getting all farms with pagination."""
        # Mock cursor_paginate method
        farm_service.cursor_paginate = AsyncMock(return_value=([], None))

        result = await farm_service.get_all_farms(
            user_id="user-123",
            sort_column="created_at",
            cursor=None,
            limit=10
        )

        items, next_cursor = result
        assert items == []
        assert next_cursor is None
        farm_service.cursor_paginate.assert_called_once()

    @pytest_asyncio.async def test_check_access_authorized(self, farm_service, sample_farm):
        """Test access check for authorized user."""
        # Should not raise exception for correct user
        await farm_service.check_access(sample_farm, "user-123")

    @pytest_asyncio.async def test_check_access_unauthorized(self, farm_service, sample_farm):
        """Test access check for unauthorized user."""
        with pytest.raises(HTTPException) as exc_info:
            await farm_service.check_access(sample_farm, "different-user")

        assert exc_info.value.status_code == 403
        assert "Access denied" in str(exc_info.value.detail)

    @pytest_asyncio.async def test_update_farm(self, farm_service, sample_farm):
        """Test farm update."""
        update_data = {
            "farm_name": "Updated Farm Name",
            "total_area": 200
        }

        await farm_service.update(sample_farm, **update_data)

        assert sample_farm.farm_name == "Updated Farm Name"
        assert sample_farm.total_area == 200
        farm_service.db.commit.assert_called_once()

    @pytest_asyncio.async def test_delete_farm(self, farm_service, sample_farm):
        """Test farm deletion."""
        farm_service.db.delete = AsyncMock()

        await farm_service.delete(sample_farm)

        farm_service.db.delete.assert_called_once_with(sample_farm)
        farm_service.db.commit.assert_called_once()


class TestFarmRoutes:
    """Integration tests for farm routes."""

    @pytest_asyncio.async def test_add_farm_unauthorized(self, client, sample_farm_data):
        """Test farm creation without authentication."""
        response = await client.post("/farms/farms", json=sample_farm_data.model_dump())
        assert response.status_code == 401

    @pytest_asyncio.async def test_get_all_farms_unauthorized(self, client):
        """Test get all farms without authentication."""
        response = await client.get("/farms/farms?sort_column=created_at")
        assert response.status_code == 401

    @pytest_asyncio.async def test_get_farm_unauthorized(self, client):
        """Test get specific farm without authentication."""
        response = await client.get("/farms/farm/farm-123")
        assert response.status_code == 401

    @pytest_asyncio.async def test_update_farm_unauthorized(self, client, sample_farm_data):
        """Test farm update without authentication."""
        response = await client.put("/farms/farm/farm-123", json=sample_farm_data.model_dump())
        assert response.status_code == 401

    @pytest_asyncio.async def test_assign_crop_unauthorized(self, client):
        """Test crop assignment without authentication."""
        response = await client.patch("/farms/farm/farm-123?crop_id=crop-123")
        assert response.status_code == 401

    @pytest_asyncio.async def test_delete_farm_unauthorized(self, client):
        """Test farm deletion without authentication."""
        response = await client.delete("/farms/farm/farm-123")
        assert response.status_code == 401


class TestFarmModels:
    """Tests for farm models and schemas."""

    def test_farm_model_validation(self):
        """Test FarmModel schema validation."""
        farm_data = {
            "farm_name": "Test Farm",
            "total_area": 100,
            "location": "Test Location",
            "crop": "corn"
        }
        farm = FarmModel(**farm_data)
        assert farm.farm_name == "Test Farm"
        assert farm.total_area == 100
        assert farm.location == "Test Location"
        assert farm.crop == "corn"

    def test_farm_model_optional_crop(self):
        """Test FarmModel with optional crop field."""
        farm_data = {
            "farm_name": "Test Farm",
            "total_area": 100,
            "location": "Test Location"
        }
        farm = FarmModel(**farm_data)
        assert farm.farm_name == "Test Farm"
        assert farm.crop is None

    def test_farm_entity_creation(self):
        """Test Farm entity creation."""
        farm = Farms(
            farm_id="farm-123",
            farm_name="Test Farm",
            total_area=100,
            user_id="user-123",
            location="Test Location",
            crop_id="crop-123"
        )
        assert farm.farm_id == "farm-123"
        assert farm.farm_name == "Test Farm"
        assert farm.user_id == "user-123"

    def test_farm_model_validation_errors(self):
        """Test FarmModel validation with invalid data."""
        with pytest.raises(Exception):  # Pydantic validation error
            FarmModel(
                farm_name="",  # Empty name should fail
                total_area=-1,  # Negative area should fail
                location="Test Location"
            )