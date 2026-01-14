import pytest
from fastapi import status
from unittest.mock import patch
import fakeredis.aioredis
from user_service.main import app
from common.security import get_token_payload

# Base payload matching the UserRegister schema requirements
VALID_USER_DATA = {
    "email": "router_test@example.com",
    "password": "SafePassword123!",
    "password_confirm": "SafePassword123!",
    "first_name": "Auth",
    "last_name": "Tester",
    "middle_name": "Route"
}

@pytest.fixture(autouse=True)
def mock_redis_client():
    """
    Patch the real redis_client used by the services with a FakeRedis instance.
    This prevents 'ConnectionError' during logout and refresh tests.
    """
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with patch("common.redis_config.redis_client", fake_redis):
        yield fake_redis

@pytest.mark.asyncio
async def test_register_new_user_api(client):
    """
    Test POST /auth/register.
    Note: Requires 'await' in auth.py router to avoid ResponseValidationError.
    """
    response = await client.post("/auth/register", json=VALID_USER_DATA)
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["email"] == VALID_USER_DATA["email"]
    assert "id" in data

@pytest.mark.asyncio
async def test_login_api(client, user_service):
    """Test POST /auth/token to receive access and refresh tokens."""
    # 1. Ensure user exists
    from user_service.schemas import UserRegister
    await user_service.create_user(UserRegister(**VALID_USER_DATA))
    
    # 2. Attempt login
    login_payload = {
        "email": VALID_USER_DATA["email"],
        "password": VALID_USER_DATA["password"]
    }
    response = await client.post("/auth/token", json=login_payload)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_logout_api(client):
    """Test POST /auth/logout using dependency overrides."""
    # Mock the token payload as if a user is logged in
    mock_payload = {"sub": "user-123", "jti": "some-jti-uuid", "exp": 9999999999}
    
    app.dependency_overrides[get_token_payload] = lambda: mock_payload
    
    try:
        # Fake token header to satisfy HTTPBearer
        headers = {"Authorization": "Bearer fake-token"}
        response = await client.post("/auth/logout", headers=headers)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["detail"] == "Successfully logged out"
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_refresh_tokens_api(client, user_service, auth_service):
    """Test POST /auth/refresh to get a new token pair."""
    # 1. Setup: Create user and get a real refresh token
    from user_service.schemas import UserRegister, UserLogin
    await user_service.create_user(UserRegister(**VALID_USER_DATA))
    login_result = await auth_service.login_user(UserLogin(
        email=VALID_USER_DATA["email"], 
        password=VALID_USER_DATA["password"]
    ))
    
    refresh_token = login_result.refresh_token
    
    # 2. Call refresh endpoint
    refresh_payload = {"refresh_token": refresh_token}
    response = await client.post("/auth/refresh", json=refresh_payload)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data