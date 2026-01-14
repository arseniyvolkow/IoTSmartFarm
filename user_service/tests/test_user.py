import pytest
import pytest_asyncio
from fastapi import status, HTTPException
from user_service.main import app
from user_service.dependencies import get_current_user, get_token_payload
from user_service.schemas import UserRegister

# Test data aligned with schemas
VALID_USER_PAYLOAD = {
    "email": "user_route@example.com",
    "password": "SafePassword123!",
    "password_confirm": "SafePassword123!",
    "first_name": "John",
    "last_name": "Doe",
    "middle_name": "User"
}

@pytest_asyncio.fixture
async def authenticated_user(user_service):
    """
    Helper fixture to create a user in the DB for routing tests.
    """
    return await user_service.create_user(UserRegister(**VALID_USER_PAYLOAD))

@pytest.mark.asyncio
async def test_get_my_profile_api(client, authenticated_user):
    """Test GET /user/me retrieves the currently logged-in user's data."""
    # Override dependencies to simulate an active session
    app.dependency_overrides[get_token_payload] = lambda: {"sub": authenticated_user.id}
    app.dependency_overrides[get_current_user] = lambda: authenticated_user
    
    try:
        response = await client.get("/user/me")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email"] == authenticated_user.email
        assert data["id"] == authenticated_user.id
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_update_my_profile_api(client, authenticated_user):
    """
    Test PUT /user/me profile update logic for all personal fields.
    """
    app.dependency_overrides[get_token_payload] = lambda: {"sub": authenticated_user.id}
    app.dependency_overrides[get_current_user] = lambda: authenticated_user
    
    new_email = "updated_route@example.com"
    update_data = {
        "email": new_email,
        "first_name": "Alexander",
        "last_name": "Hamilton",
        "middle_name": "Treasury"
    }
    
    try:
        response = await client.put("/user/me", json=update_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Verify all fields were updated (assuming UserService logic was updated)
        assert data["email"] == new_email
        assert data["first_name"] == "Alexander"
        assert data["last_name"] == "Hamilton"
        assert data["middle_name"] == "Treasury"
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_delete_my_profile_api(client, authenticated_user):
    """Test DELETE /user/me soft deletion."""
    app.dependency_overrides[get_token_payload] = lambda: {"sub": authenticated_user.id}
    app.dependency_overrides[get_current_user] = lambda: authenticated_user
    
    try:
        response = await client.delete("/user/me")
        assert response.status_code == status.HTTP_204_NO_CONTENT
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_admin_get_user_by_id_api(client, authenticated_user):
    """Test admin-only route to view any user profile."""
    # Simulate an admin payload for the CheckAccess dependency
    admin_payload = {
        "sub": "admin-id",
        "access": {"users": {"r": 1, "w": 1, "d": 1}},
        "g_perms": {"r_all": False, "w_all": False}
    }
    app.dependency_overrides[get_token_payload] = lambda: admin_payload
    
    try:
        response = await client.get(f"/user/{authenticated_user.id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == authenticated_user.id
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_admin_rbac_denial_api(client):
    """Verify that a user without 'users' permissions receives 403 Forbidden."""
    regular_payload = {
        "sub": "normal-user",
        "access": {}, 
        "g_perms": {}
    }
    app.dependency_overrides[get_token_payload] = lambda: regular_payload
    
    try:
        response = await client.get("/user/")
        assert response.status_code == status.HTTP_403_FORBIDDEN
    finally:
        app.dependency_overrides.clear()