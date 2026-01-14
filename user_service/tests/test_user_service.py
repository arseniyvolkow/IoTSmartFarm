import pytest
from fastapi import HTTPException, status
from user_service.schemas import UserRegister, UserUpdate

# Common data to avoid repetition and ensure schema requirements are met
VALID_USER_PAYLOAD = {
    "email": "test@example.com",
    "password": "SafePassword123!",
    "password_confirm": "SafePassword123!",
    "first_name": "John",
    "last_name": "Doe",
    "middle_name": "Quincy"
}

@pytest.mark.asyncio
async def test_create_user_success(user_service, db_session):
    """Test successful user creation with all required fields."""
    new_user_data = UserRegister(**VALID_USER_PAYLOAD)
    
    user = await user_service.create_user(new_user_data)
    
    assert user.email == VALID_USER_PAYLOAD["email"]
    assert user.is_active is True
    assert user.hashed_password != VALID_USER_PAYLOAD["password"]

@pytest.mark.asyncio
async def test_create_user_duplicate_email(user_service, db_session):
    """Test registration with existing email."""
    data = UserRegister(**VALID_USER_PAYLOAD)
    await user_service.create_user(data)
    
    with pytest.raises(HTTPException) as exc:
        await user_service.create_user(data)
    
    assert exc.value.status_code == 400
    assert "Email already registered" in exc.value.detail

@pytest.mark.asyncio
async def test_create_user_password_validation(user_service):
    """Test the password complexity regex logic."""
    invalid_passwords = [
        "short1!", 
        "NOLOWERCASE123!", 
        "nouppercase123!", 
        "NoDigitsLetters!", 
        "NoSpecialChar123"
    ]
    
    for pwd in invalid_passwords:
        payload = VALID_USER_PAYLOAD.copy()
        payload.update({
            "email": f"fail_{pwd}@test.com",
            "password": pwd,
            "password_confirm": pwd
        })
        
        try:
            data = UserRegister(**payload)
            with pytest.raises(HTTPException) as exc:
                await user_service.create_user(data)
            assert exc.value.status_code == 400
        except Exception as e:
            assert "validation error" in str(e).lower() or "400" in str(e)

@pytest.mark.asyncio
async def test_get_user_by_id_flow(user_service, db_session):
    """Test retrieving user by ID."""
    data = UserRegister(**VALID_USER_PAYLOAD)
    created_user = await user_service.create_user(data)
    
    found_user = await user_service.get_user_by_id(created_user.id)
    assert found_user.id == created_user.id

@pytest.mark.asyncio
async def test_soft_delete_user(user_service, db_session):
    """Test soft delete sets is_active to False."""
    user = await user_service.create_user(UserRegister(**VALID_USER_PAYLOAD))
    await user_service.soft_delete_user(user.id)
    
    await db_session.refresh(user)
    assert user.is_active is False

@pytest.mark.asyncio
async def test_update_user_logic(user_service, db_session):
    """
    Test updating user attributes including the newly added 
    first_name, last_name, and middle_name fields.
    """
    # Create initial user
    user1 = await user_service.create_user(UserRegister(**VALID_USER_PAYLOAD))
    old_password_hash = user1.hashed_password
    
    # Create second user to test email collision
    payload2 = VALID_USER_PAYLOAD.copy()
    payload2.update({"email": "taken@test.com"})
    await user_service.create_user(UserRegister(**payload2))
    
    # 1. Update all available fields successfully
    update_data = UserUpdate(
        email="new_email@test.com",
        password="NewSecret456!",
        first_name="Alexander",
        last_name="Hamilton",
        middle_name="Treasury",
        is_active=True
    )
    
    updated = await user_service.update_user(user1.id, update_data)
    
    # Verify updates in the returned object
    assert updated.email == "new_email@test.com"
    assert updated.hashed_password != old_password_hash
    assert updated.first_name == "Alexander"
    assert updated.last_name == "Hamilton"
    assert updated.middle_name == "Treasury"

    # 2. Update email to taken one (Fail)
    with pytest.raises(HTTPException) as exc:
        await user_service.update_user(user1.id, UserUpdate(email="taken@test.com"))
    assert exc.value.status_code == 400

@pytest.mark.asyncio
async def test_assign_role_integration(user_service, rbac_service, db_session):
    """Test role assignment flow."""
    user = await user_service.create_user(UserRegister(**VALID_USER_PAYLOAD))
    role_name = "admin"
    await rbac_service.create_role(role_name)
    
    updated_user = await user_service.assign_role_to_user(user.id, role_name)
    
    await db_session.refresh(updated_user, ["role"])
    assert updated_user.role.name == role_name