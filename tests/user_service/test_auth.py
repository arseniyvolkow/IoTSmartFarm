import pytest
from fastapi.testclient import TestClient
from user_service.models import Users
from user_service.utils import bcrypt_context, get_current_user
from user_service.main import app
from sqlalchemy.ext.asyncio import AsyncSession


def test_create_user_success(client: TestClient):
    """Tests that a user is created successfully."""
    response = client.post(
        "/auth/create_user",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "Password123!",
            "contact_number": "1234567890",
            "role": "user",
        },
    )
    assert response.status_code == 201


def test_create_duplicate_email(client: TestClient):
    """Tests that a duplicate email is rejected."""
    # First user request
    client.post(
        "/auth/create_user",
        json={
            "username": "user1",
            "email": "duplicate@example.com",
            "password": "Password123!",
            "contact_number": "1234567890",
            "role": "user",
        },
    )
    # Second user request with the same email
    response = client.post(
        "/auth/create_user",
        json={
            "username": "user2",
            "email": "duplicate@example.com",
            "password": "Password123!",
            "contact_number": "9876543210",
            "role": "user",
        },
    )
    assert response.status_code == 400


def test_create_duplicate_username(client: TestClient):
    """Tests that a duplicate username is rejected."""
    # First user request
    client.post(
        "/auth/create_user",
        json={
            "username": "duplicateuser",
            "email": "test1@example.com",
            "password": "Password123!",
            "contact_number": "1234567890",
            "role": "user",
        },
    )
    # Second user request with the same username
    response = client.post(
        "/auth/create_user",
        json={
            "username": "duplicateuser",
            "email": "test2@example.com",
            "password": "Password123!",
            "contact_number": "9876543210",
            "role": "user",
        },
    )
    assert response.status_code == 400


def test_create_password_is_not_strong(client: TestClient):
    """Tests that a weak password is rejected."""
    response = client.post(
        "/auth/create_user",
        json={
            "username": "userweakpass",
            "email": "weak@example.com",
            "password": "weak",
            "contact_number": "1234567890",
            "role": "user",
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_token_success(client: TestClient, db_session: AsyncSession):
    """Tests that a valid user can successfully obtain a token."""
    # 1. Arrange: Manually create a user in the test database.
    hashed_password = bcrypt_context.hash("Password123!")
    test_user = Users(
        username="testloginuser",
        email="login@example.com",
        hashed_password=hashed_password,
        role="user",
        contact_number="123456789",
    )

    db_session.add(test_user)
    await db_session.commit()

    # 2. Act: Attempt to log in.
    response = client.post(
        "/auth/token", data={"username": "testloginuser", "password": "Password123!"}
    )

    # 3. Assert: Check for a successful response.
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_get_token_failure(client: TestClient, db_session: AsyncSession):
    """Tests that an invalid user cannot successfully obtain a token."""
    hashed_password = bcrypt_context.hash("Password123!")
    test_user = Users(
        username="testloginuser",
        email="login@example.com",
        hashed_password=hashed_password,
        role="user",
        contact_number="123456789",
    )

    db_session.add(test_user)
    await db_session.commit()

    response = client.post(
        "/auth/token", data={"username": "testloginuser", "password": "Password122!"}
    )

    assert response.status_code == 401


def test_get_current_user_success(client: TestClient):
    """Tests that get_current_user returns the expected user data."""
    fake_user = {"username": "fakeuser", "id": 123, "role": "admin"}

    def override_get_current_user():
        """This mock function will be used instead of the real one."""
        return fake_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        response = client.get(
            "/auth/get_current_user", headers={"Authorization": "Bearer fake-token"}
        )

        assert response.status_code == 200
        assert response.json() == {
            "username": "fakeuser",
            "id": 123,
            "role": "admin",
        }
    finally:
        # Clean up the override
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]


            