from fastapi.testclient import TestClient
from user_service.main import app
from user_service.utils import get_current_user, bcrypt_context
from user_service.models import Users
from sqlalchemy.ext.asyncio import AsyncSession
import pytest


@pytest.mark.asyncio
async def test_user_info(client: TestClient, db_session: AsyncSession):
    hashed_password = bcrypt_context.hash("Password123!")
    test_user = Users(
        user_id=123,
        username="fakeuser",
        email="fake@example.com",
        hashed_password=hashed_password,
        role="admin",
        contact_number="123456789",
    )

    db_session.add(test_user)
    await db_session.commit()

    fake_user = {"username": "fakeuser", "id": 123, "role": "admin"}

    def override_get_current_user():
        """This mock function will be used instead of the real one."""
        return fake_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        response = client.get(
            "/user/info", headers={"Authorization": "Bearer fake-token"}
        )

        assert response.status_code == 200
        assert response.json() == {
            "username": "fakeuser",
            "user_id": 123,
            "email": "fake@example.com",
            "role": "admin",
            "contact_number": "123456789",
        }
    finally:
        # Clean up the override
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]


@pytest.mark.asyncio
async def test_user_info_user_not_found(client: TestClient):
    """Test that user_info returns 404 when user doesn't exist in database."""

    # Mock get_current_user to return a user ID that doesn't exist in the database
    fake_user = {"username": "nonexistent", "id": 999, "role": "user"}

    def override_get_current_user():
        return fake_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        response = client.get(
            "/user/info", headers={"Authorization": "Bearer fake-token"}
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "User not found."

    finally:
        # Clean up the override
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]


@pytest.mark.asyncio
async def test_change_password_success(client: TestClient, db_session: AsyncSession):
    """Test successful password change."""

    # 1. Create a user in the database with a known password
    old_password = "OldPassword123!"
    hashed_old_password = bcrypt_context.hash(old_password)

    test_user = Users(
        user_id=123,
        username="testuser",
        email="test@example.com",
        hashed_password=hashed_old_password,
        role="user",
        contact_number="123456789",
    )

    db_session.add(test_user)
    await db_session.commit()

    # 2. Mock authentication
    fake_user = {"username": "testuser", "id": 123, "role": "user"}

    def override_get_current_user():
        return fake_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        # 3. Make the password change request
        response = client.put(
            "/user/change-password",
            json={"old_password": old_password, "new_password": "NewPassword123!"},
            headers={"Authorization": "Bearer fake-token"},
        )

        # 4. Verify the response
        assert response.status_code == 204  # HTTP_204_NO_CONTENT
        assert response.text == ""  # 204 responses typically have no content

        # 5. Verify the password was actually changed in the database
        await db_session.refresh(test_user)

        # Old password should no longer work
        assert not bcrypt_context.verify(old_password, test_user.hashed_password)

        # New password should work
        assert bcrypt_context.verify("NewPassword123!", test_user.hashed_password)

    finally:
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]


@pytest.mark.asyncio
async def test_change_password_wrong_old_password(
    client: TestClient, db_session: AsyncSession
):
    """Test password change with incorrect old password."""

    # 1. Create a user with a known password
    correct_old_password = "CorrectPassword123!"
    hashed_password = bcrypt_context.hash(correct_old_password)

    test_user = Users(
        user_id=124,
        username="testuser2",
        email="test2@example.com",
        hashed_password=hashed_password,
        role="user",
        contact_number="123456789",
    )

    db_session.add(test_user)
    await db_session.commit()

    # 2. Mock authentication
    fake_user = {"username": "testuser2", "id": 124, "role": "user"}

    def override_get_current_user():
        return fake_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        # 3. Try to change password with wrong old password
        response = client.put(
            "/user/change-password",
            json={
                "old_password": "WrongOldPassword123!",  # This is incorrect
                "new_password": "NewPassword123!",
            },
            headers={"Authorization": "Bearer fake-token"},
        )

        # 4. Verify the response
        assert response.status_code == 401  # HTTP_401_UNAUTHORIZED
        assert response.json()["detail"] == "Current password is incorrect"

        # 5. Verify the password was NOT changed
        await db_session.refresh(test_user)
        assert bcrypt_context.verify(correct_old_password, test_user.hashed_password)

    finally:
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]


@pytest.mark.asyncio
async def test_change_password_user_not_found(client: TestClient):
    """Test password change when user doesn't exist in database."""

    # Mock authentication to return a user ID that doesn't exist
    fake_user = {"username": "nonexistent", "id": 999, "role": "user"}

    def override_get_current_user():
        return fake_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        response = client.put(
            "/user/change-password",
            json={
                "old_password": "SomePassword123!",
                "new_password": "NewPassword123!",
            },
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "User not found"

    finally:
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]


def test_change_password_invalid_request_data(client: TestClient):
    """Test password change with invalid request body."""

    # Mock authentication (user exists doesn't matter for this test)
    fake_user = {"username": "testuser", "id": 123, "role": "user"}

    def override_get_current_user():
        return fake_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        response = client.put(
            "/user/change-password",
            json={
                "old_password": "OldPassword123!"
                # Missing new_password
            },
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 422

        response = client.put(
            "/user/change-password",
            json={"old_password": "", "new_password": ""},
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code in [401, 422]

    finally:
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]


def test_change_password_no_auth_token(client: TestClient):
    """Test password change without authentication token."""

    response = client.put(
        "/user/change-password",
        json={"old_password": "OldPassword123!", "new_password": "NewPassword123!"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_change_password_weak_new_password(
    client: TestClient, db_session: AsyncSession
):
    """Test password change with weak new password (if you have password validation)."""

    old_password = "OldPassword123!"
    hashed_old_password = bcrypt_context.hash(old_password)

    test_user = Users(
        user_id=125,
        username="testuser3",
        email="test3@example.com",
        hashed_password=hashed_old_password,
        role="user",
        contact_number="123456789",
    )

    db_session.add(test_user)
    await db_session.commit()

    fake_user = {"username": "testuser3", "id": 125, "role": "user"}

    def override_get_current_user():
        return fake_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        # 3. Try to change to a weak password
        response = client.put(
            "/user/change-password",
            json={
                "old_password": old_password,
                "new_password": "weak",  # Weak password
            },
            headers={"Authorization": "Bearer fake-token"},
        )

        # 4. This should fail validation (if you have password strength validation)
        # If you don't have validation, this test might pass with 204
        # Adjust based on your ChangePassword model validation
        assert response.status_code in [400, 422]  # Validation error

    finally:
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]


@pytest.mark.asyncio
async def test_change_number(client: TestClient, db_session: AsyncSession):
    hashed_password = bcrypt_context.hash("Password123!")

    test_user = Users(
        user_id=123,
        username="testuser",
        email="test@example.com",
        hashed_password=hashed_password,
        role="user",
        contact_number="123456789",
    )

    db_session.add(test_user)
    await db_session.commit()

    fake_user = {"username": "testuser", "id": 123, "role": "user"}

    def override_get_current_user():
        return fake_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        # 3. Make the password change request
        response = client.put(
            "/user/change-number",
            json={"new_number": "987654321"},
            headers={"Authorization": "Bearer fake-token"},
        )
        # 4. Verify the response
        assert response.status_code == 204  # HTTP_204_NO_CONTENT
        assert response.text == ""  # 204 responses typically have no content

    finally:
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]


@pytest.mark.asyncio
async def test_change_number_user_not_found(client: TestClient, db_session: AsyncSession):
    fake_user = {"username": "testuser", "id": 123, "role": "user"}

    def override_get_current_user():
        return fake_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        response = client.put(
            "/user/change-number",
            json={"new_number": "987654321"},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "User not found"
    finally:
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]



@pytest.mark.asyncio
async def test_change_number_invalid_request_data(client: TestClient, db_session: AsyncSession):
    fake_user = {"username": "testuser", "id": 123, "role": "user"}

    def override_get_current_user():
        return fake_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        response = client.put(
            "/user/change-number",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert response.status_code in [401, 422]
    finally:
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
