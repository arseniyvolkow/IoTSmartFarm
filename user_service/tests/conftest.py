import pytest
import pytest_asyncio
import os

# Set environment variables before app imports to prevent configuration errors
os.environ["SECRET_KEY"] = "test-secret-key-123"
os.environ["ALGORITHM"] = "HS256"
os.environ["REDIS_HOST"] = "localhost"

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from httpx import AsyncClient, ASGITransport
from user_service.main import app
from user_service.database import Base, get_db
from user_service.services.auth_service import AuthService
from user_service.services.rbac_service import RBACService
from user_service.services.user_service import UserService
from common.redis_config import redis_client

# SQLite in-memory is used for speed and isolation during tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine_test = create_async_engine(TEST_DATABASE_URL)
TestingSessionLocal = async_sessionmaker(
    bind=engine_test, 
    class_=AsyncSession, 
    expire_on_commit=False
)

@pytest_asyncio.fixture(scope="session", autouse=True)
async def cleanup_resources():
    """
    Ensures all background connections are closed before exiting to prevent hangs.
    Replaces deprecated close() with aclose() for Redis.
    """
    yield
    # Close the Redis connection pool
    if redis_client:
        # Replaced close() with aclose() to fix DeprecationWarning
        await redis_client.aclose()
    
    # Dispose of the SQLAlchemy engine using the local global variable
    await engine_test.dispose()

@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Provides a fresh, clean database session for every individual test."""
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestingSessionLocal() as session:
        yield session
        
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    """Async HTTP client for testing FastAPI endpoints (Integration Tests)."""
    async def _get_test_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_test_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.fixture
def auth_service(db_session):
    """Fixture to inject AuthService into tests."""
    return AuthService(db_session)

@pytest.fixture
def rbac_service(db_session):
    """Fixture to inject RBACService into tests."""
    return RBACService(db_session)

@pytest.fixture
def user_service(db_session):
    """Fixture to inject UserService into tests."""
    return UserService(db_session)