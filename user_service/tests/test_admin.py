import pytest
from fastapi import status
from user_service.main import app
from common.security import get_token_payload

# Mock payload that has full access to the "roles" resource
ADMIN_PAYLOAD = {
    "sub": "admin-user-id",
    "email": "admin@example.com",
    "g_perms": {"r_all": False, "w_all": False},
    "access": {
        "roles": {"r": 1, "w": 1, "d": 1}
    }
}

@pytest.fixture(autouse=True)
def override_security():
    """
    Automatically override the security dependency for all tests in this file.
    This bypasses JWT validation and provides a pre-defined admin payload.
    """
    async def mock_payload():
        return ADMIN_PAYLOAD

    app.dependency_overrides[get_token_payload] = mock_payload
    yield
    app.dependency_overrides.pop(get_token_payload, None)

@pytest.mark.asyncio
async def test_create_role_api(client):
    """Test POST /admin/roles/ to create a new role."""
    payload = {
        "name": "moderator",
        "can_read_all": True,
        "can_write_all": False
    }
    response = await client.post("/admin/roles/", json=payload)
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == "moderator"
    assert "id" in data

@pytest.mark.asyncio
async def test_get_all_roles_api(client, rbac_service):
    """Test GET /admin/roles/ returns a list of roles."""
    # Ensure at least one role exists
    await rbac_service.create_role("test_role")
    
    response = await client.get("/admin/roles/")
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), list)
    assert len(response.json()) >= 1

@pytest.mark.asyncio
async def test_set_permission_for_role_api(client, rbac_service, db_session):
    """Test POST /admin/roles/{role_name}/permissions (UPSERT logic)."""
    # 1. Create a role first
    role_name = "editor"
    await rbac_service.create_role(role_name)
    
    # FIX: Clear the session cache.
    # Since the app and test share the same db_session, and expire_on_commit is False,
    # the Role object created above is cached. We must expire it so the API
    # call is forced to reload the Role and its new access_list from the DB.
    db_session.expire_all()
    
    # 2. Set permissions
    perm_payload = {
        "resource": "farms",
        "can_read": True,
        "can_write": True,
        "can_delete": False
    }
    response = await client.post(f"/admin/roles/{role_name}/permissions", json=perm_payload)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    # Find the permission in the returned access_list
    perms = [p for p in data["access_list"] if p["resource"] == "farms"]
    assert len(perms) == 1
    assert perms[0]["can_write"] is True

@pytest.mark.asyncio
async def test_get_role_details_api(client, rbac_service):
    """Test GET /admin/roles/{role_name}."""
    role_name = "viewer"
    await rbac_service.create_role(role_name)
    
    response = await client.get(f"/admin/roles/{role_name}")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["name"] == role_name

@pytest.mark.asyncio
async def test_delete_role_api(client, rbac_service):
    """Test DELETE /admin/roles/{role_name}."""
    role_name = "to_be_deleted"
    await rbac_service.create_role(role_name)
    
    response = await client.delete(f"/admin/roles/{role_name}")
    assert response.status_code == status.HTTP_204_NO_CONTENT
    
    # Verify it's gone
    check = await client.get(f"/admin/roles/{role_name}")
    assert check.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.asyncio
async def test_rbac_restriction_api(client):
    """
    Verify that the CheckAccess dependency actually works 
    by simulating a user with NO permissions.
    """
    async def mock_no_perms_payload():
        return {"sub": "poor-user", "access": {}, "g_perms": {}}
    
    # Temporarily override with a restricted user
    app.dependency_overrides[get_token_payload] = mock_no_perms_payload
    
    response = await client.get("/admin/roles/")
    # Should return 403 Forbidden because CheckAccess("roles", "read") will fail
    assert response.status_code == status.HTTP_403_FORBIDDEN