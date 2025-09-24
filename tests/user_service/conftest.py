from dotenv import load_dotenv
load_dotenv(dotenv_path=".env.test")

import pytest
import pytest_asyncio
import asyncio
from typing import AsyncGenerator
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from user_service.main import app
from user_service.database import Base, get_db

# Database setup for an in-memory SQLite database
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(SQLALCHEMY_DATABASE_URL, echo=True)
TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Asynchronous override for the get_db dependency
async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session

# Apply the dependency override to the app
app.dependency_overrides[get_db] = override_get_db

# Proper event loop fixture for pytest-asyncio
@pytest_asyncio.fixture(scope="session")
async def setup_database():
    """Create database tables once for the entire test session."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

# Clean database fixture for each test
@pytest_asyncio.fixture(scope="function")
async def clean_db():
    """Clean all tables before each test."""
    async with engine.begin() as conn:
        # Get all table names and truncate them
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

@pytest.fixture(scope="function")
def client(clean_db) -> TestClient:
    """Provide a TestClient with a clean database."""
    return TestClient(app)

# Helper fixture to get a database session for test data setup
@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for test data setup."""
    async with TestingSessionLocal() as session:
        yield session