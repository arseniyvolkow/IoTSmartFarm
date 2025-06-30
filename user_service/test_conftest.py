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
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_user.db"

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
def sample_user_data():
    """Sample user data for testing."""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "TestPass123!",
        "contact_number": "+1234567890",
        "role": "farmer"
    }


@pytest.fixture
def sample_admin_data():
    """Sample admin user data for testing."""
    return {
        "username": "admin",
        "email": "admin@example.com",
        "password": "AdminPass123!",
        "contact_number": "+0987654321",
        "role": "admin"
    }


@pytest.fixture
def login_data():
    """Sample login data for testing."""
    return {
        "username": "testuser",
        "password": "TestPass123!"
    }


@pytest.fixture
def mock_jwt_payload():
    """Mock JWT payload for testing."""
    return {
        "username": "testuser",
        "id": 1,
        "role": "farmer",
        "exp": 9999999999  # Far future expiration
    }


@pytest.fixture
def invalid_passwords():
    """List of invalid passwords for testing validation."""
    return [
        "short",  # Too short
        "nouppercase123!",  # No uppercase
        "NOLOWERCASE123!",  # No lowercase
        "NoDigits!",  # No digits
        "NoSpecialChars123",  # No special characters
        "",  # Empty
    ]


@pytest.fixture
def valid_passwords():
    """List of valid passwords for testing."""
    return [
        "ValidPass123!",
        "AnotherGood456@",
        "StrongPassword789#",
        "Complex$Password1"
    ]