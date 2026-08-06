from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from common.auth.security import UserIdentity, get_current_user_identity
from sensor_data_service.database import Settings
from sensor_data_service.dependencies import (
    get_influx_service,
    get_mqtt_service,
    get_redis_service,
    get_settings,
)
from sensor_data_service.main import app


@pytest.fixture
def mock_influx_service():
    mock = AsyncMock()
    mock.ping.return_value = True
    return mock


@pytest.fixture
def mock_mqtt_service():
    mock = AsyncMock()
    mock.is_connected.return_value = True
    return mock


@pytest.fixture
def mock_redis_service():
    mock = AsyncMock()
    mock.is_connected.return_value = True
    return mock


@pytest.fixture
def mock_settings():
    settings = Settings()
    settings.INFLUXDB_URL = "http://mock:8086"
    settings.INFLUXDB_TOKEN = "mock_token"
    settings.INFLUXDB_ORG = "mock_org"
    settings.INFLUXDB_BUCKET = "mock_bucket"
    settings.MQTT_BROKER = "mock_broker"
    settings.MQTT_PORT = 1883
    settings.REDIS_HOST = "mock_redis"
    settings.REDIS_PORT = 6379
    return settings


@pytest.fixture
def override_dependencies(
    mock_influx_service, mock_mqtt_service, mock_redis_service, mock_settings
):
    app.dependency_overrides[get_influx_service] = lambda: mock_influx_service
    app.dependency_overrides[get_mqtt_service] = lambda: mock_mqtt_service
    app.dependency_overrides[get_redis_service] = lambda: mock_redis_service
    app.dependency_overrides[get_settings] = lambda: mock_settings

    admin_user = UserIdentity(
        {"sub": "admin", "g_perms": {"w_all": True, "r_all": True}}
    )
    app.dependency_overrides[get_current_user_identity] = lambda: admin_user

    yield

    app.dependency_overrides.clear()


import httpx
import pytest_asyncio


@pytest_asyncio.fixture
async def async_client(override_dependencies):
    transport = httpx.ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
