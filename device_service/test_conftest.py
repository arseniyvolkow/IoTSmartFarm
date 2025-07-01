import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from httpx import AsyncClient
from unittest.mock import Mock, AsyncMock
import os
from .main import app
from .models import Base
from .database import get_db
from faker import Faker

fake = Faker()

# Test database URL - using SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL, 
    echo=False,
    connect_args={"check_same_thread": False}
)

# Create test session factory
TestSessionLocal = sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


@pytest_asyncio.fixture
async def test_db():
    """Create test database tables and provide a database session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestSessionLocal() as session:
        yield session
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(test_db):
    """Create test client with database dependency override."""
    def override_get_db():
        return test_db
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture
def mock_user():
    """Mock user data for testing."""
    return {
        "username": "testuser",
        "id": 1,
        "role": "farmer"
    }


@pytest.fixture
def mock_jwt_token():
    """Mock JWT token for authentication testing."""
    return "mock_jwt_token"


@pytest.fixture
def sample_device_data():
    """Sample device data for testing."""
    return {
        "username": "testuser",
        "password": "TestPass123!",
        "unique_device_id": fake.uuid4(),
        "device_ip_address": fake.ipv4(),
        "model_number": "TEST-001",
        "firmware_version": "1.0.0",
        "sensors_list": [
            {
                "sensor_type": "temperature",
                "units_of_measure": "celsius",
                "max_value": 50.0,
                "min_value": -10.0
            },
            {
                "sensor_type": "humidity",
                "units_of_measure": "percentage",
                "max_value": 100.0,
                "min_value": 0.0
            }
        ]
    }


@pytest.fixture
def sample_farm_data():
    """Sample farm data for testing."""
    return {
        "farm_name": "Test Farm",
        "total_area": 100,
        "location": "Test Location",
        "crop": "corn"
    }