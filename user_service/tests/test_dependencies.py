import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException, status
from user_service.dependencies import get_current_user, get_user_service, get_auth_service, get_rbac_service
from user_service.services.user_service import UserService
from user_service.services.auth_service import AuthService
from user_service.services.rbac_service import RBACService
from user_service.models import User

@pytest.mark.asyncio
async def test_get_current_user_success(db_session):
    """Test successfully retrieving an active user from the database."""
    # 1. Setup: Create a user in the test SQLite DB
    user_id = "test-uuid-123"
    new_user = User(
        id=user_id, 
        email="active@example.com", 
        hashed_password="...", 
        is_active=True
    )
    db_session.add(new_user)
    await db_session.commit()
    
    # 2. Execute: Call the dependency with a mock payload
    payload = {"sub": user_id}
    result = await get_current_user(db=db_session, payload=payload)
    
    # 3. Verify
    assert result.id == user_id
    assert result.is_active is True

@pytest.mark.asyncio
async def test_get_current_user_not_found(db_session):
    """Test 401 error when the user ID in the token doesn't exist in the DB."""
    payload = {"sub": "non-existent-uuid"}
    
    with pytest.raises(HTTPException) as exc:
        await get_current_user(db=db_session, payload=payload)
    
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "User not found" in exc.value.detail

@pytest.mark.asyncio
async def test_get_current_user_inactive(db_session):
    """Test 401 error when the user is found but marked as inactive."""
    # 1. Setup: Create an inactive user
    user_id = "inactive-uuid"
    inactive_user = User(
        id=user_id, 
        email="inactive@example.com", 
        hashed_password="...", 
        is_active=False
    )
    db_session.add(inactive_user)
    await db_session.commit()
    
    # 2. Execute & Verify
    payload = {"sub": user_id}
    with pytest.raises(HTTPException) as exc:
        await get_current_user(db=db_session, payload=payload)
    
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "inactive" in exc.value.detail

@pytest.mark.asyncio
async def test_service_getters(db_session):
    """Verify that service factory functions return the correct class instances."""
    user_svc = await get_user_service(db_session)
    auth_svc = await get_auth_service(db_session)
    rbac_svc = await get_rbac_service(db_session)
    
    assert isinstance(user_svc, UserService)
    assert isinstance(auth_svc, AuthService)
    assert isinstance(rbac_svc, RBACService)
    
    # Verify they are all using the same DB session
    assert user_svc.db == db_session
    assert auth_svc.db == db_session
    assert rbac_svc.db == db_session