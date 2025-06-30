import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from .routers.auth import authenticate_user, create_access_token, get_current_user
from .models import Users
from .routers.auth import CreateUserRequest
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta, timezone
import os

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TestAuthenticationService:
    """Unit tests for authentication functionality."""

    @pytest_asyncio.fixture
    async def mock_db_session(self):
        """Mock database session."""
        session = Mock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.add = Mock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest_asyncio.fixture
    def sample_user(self):
        """Create a sample user for testing."""
        user = Users(
            user_id=1,
            username="testuser",
            email="test@example.com",
            hashed_password=bcrypt_context.hash("TestPass123!"),
            contact_number="+1234567890",
            role="farmer"
        )
        return user

    @pytest_asyncio.async def test_authenticate_user_success(self, mock_db_session, sample_user):
        """Test successful user authentication."""
        # Mock database query result
        mock_result = Mock()
        mock_result.scalars.return_value.first.return_value = sample_user
        mock_db_session.execute.return_value = mock_result

        result = await authenticate_user("testuser", "TestPass123!", mock_db_session)

        assert result == sample_user
        mock_db_session.execute.assert_called_once()

    @pytest_asyncio.async def test_authenticate_user_wrong_password(self, mock_db_session, sample_user):
        """Test authentication with wrong password."""
        mock_result = Mock()
        mock_result.scalars.return_value.first.return_value = sample_user
        mock_db_session.execute.return_value = mock_result

        result = await authenticate_user("testuser", "WrongPassword", mock_db_session)

        assert result is False

    @pytest_asyncio.async def test_authenticate_user_not_found(self, mock_db_session):
        """Test authentication with non-existent user."""
        mock_result = Mock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await authenticate_user("nonexistent", "TestPass123!", mock_db_session)

        assert result is False

    def test_create_access_token(self):
        """Test JWT token creation."""
        username = "testuser"
        user_id = 1
        role = "farmer"
        expires_delta = timedelta(minutes=20)

        token = create_access_token(username, user_id, role, expires_delta)

        assert isinstance(token, str)
        # Decode token to verify contents
        secret_key = os.getenv("SECRET_KEY", "test_secret")
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        assert payload["username"] == username
        assert payload["id"] == user_id
        assert payload["role"] == role

    @pytest_asyncio.async def test_get_current_user_valid_token(self):
        """Test extracting user info from valid JWT token."""
        # Create a valid token
        secret_key = os.getenv("SECRET_KEY", "test_secret")
        payload = {
            "username": "testuser",
            "id": 1,
            "role": "farmer",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=20)
        }
        token = jwt.encode(payload, secret_key, algorithm="HS256")

        result = await get_current_user(token)

        assert result["username"] == "testuser"
        assert result["id"] == 1
        assert result["role"] == "farmer"

    @pytest_asyncio.async def test_get_current_user_invalid_token(self):
        """Test extracting user info from invalid JWT token."""
        invalid_token = "invalid.jwt.token"

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(invalid_token)

        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in str(exc_info.value.detail)


class TestUserRoutes:
    """Integration tests for user routes."""

    @pytest_asyncio.async def test_create_user_success(self, client, sample_user_data, test_db):
        """Test successful user creation."""
        response = await client.post("/auth/create_user", json=sample_user_data)
        assert response.status_code == 201
        data = response.json()
        assert data["detail"] == "User created successfully"
        assert "user_id" in data

    @pytest_asyncio.async def test_create_user_duplicate_email(self, client, sample_user_data, test_db):
        """Test user creation with duplicate email."""
        # Create first user
        await client.post("/auth/create_user", json=sample_user_data)
        
        # Try to create user with same email
        duplicate_user_data = sample_user_data.copy()
        duplicate_user_data["username"] = "differentuser"
        response = await client.post("/auth/create_user", json=duplicate_user_data)
        
        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]

    @pytest_asyncio.async def test_create_user_duplicate_username(self, client, sample_user_data, test_db):
        """Test user creation with duplicate username."""
        # Create first user
        await client.post("/auth/create_user", json=sample_user_data)
        
        # Try to create user with same username
        duplicate_user_data = sample_user_data.copy()
        duplicate_user_data["email"] = "different@example.com"
        response = await client.post("/auth/create_user", json=duplicate_user_data)
        
        assert response.status_code == 400
        assert "Username already exists" in response.json()["detail"]

    @pytest_asyncio.async def test_create_user_invalid_password(self, client, sample_user_data, invalid_passwords):
        """Test user creation with invalid passwords."""
        for invalid_password in invalid_passwords:
            user_data = sample_user_data.copy()
            user_data["password"] = invalid_password
            user_data["username"] = f"user_{invalid_password[:5]}"  # Unique username
            user_data["email"] = f"user_{invalid_password[:5]}@example.com"  # Unique email
            
            response = await client.post("/auth/create_user", json=user_data)
            assert response.status_code == 400
            assert "Password must be at least 8 characters" in response.json()["detail"]

    @pytest_asyncio.async def test_create_user_valid_passwords(self, client, sample_user_data, valid_passwords):
        """Test user creation with valid passwords."""
        for i, valid_password in enumerate(valid_passwords):
            user_data = sample_user_data.copy()
            user_data["password"] = valid_password
            user_data["username"] = f"user_{i}"
            user_data["email"] = f"user_{i}@example.com"
            
            response = await client.post("/auth/create_user", json=user_data)
            assert response.status_code == 201

    @pytest_asyncio.async def test_login_success(self, client, sample_user_data, test_db):
        """Test successful login."""
        # Create user first
        await client.post("/auth/create_user", json=sample_user_data)
        
        # Login
        login_data = {
            "username": sample_user_data["username"],
            "password": sample_user_data["password"]
        }
        response = await client.post("/auth/token", data=login_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest_asyncio.async def test_login_invalid_credentials(self, client, sample_user_data, test_db):
        """Test login with invalid credentials."""
        # Create user first
        await client.post("/auth/create_user", json=sample_user_data)
        
        # Login with wrong password
        login_data = {
            "username": sample_user_data["username"],
            "password": "WrongPassword"
        }
        response = await client.post("/auth/token", data=login_data)
        
        assert response.status_code == 401
        assert "Could not validate credentials" in response.json()["detail"]

    @pytest_asyncio.async def test_login_nonexistent_user(self, client):
        """Test login with non-existent user."""
        login_data = {
            "username": "nonexistent",
            "password": "TestPass123!"
        }
        response = await client.post("/auth/token", data=login_data)
        
        assert response.status_code == 401

    @pytest_asyncio.async def test_login_for_id_success(self, client, sample_user_data, test_db):
        """Test login_for_id endpoint success."""
        # Create user first
        await client.post("/auth/create_user", json=sample_user_data)
        
        # Login for ID
        login_data = {
            "username": sample_user_data["username"],
            "password": sample_user_data["password"]
        }
        response = await client.post("/auth/login_for_id", data=login_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert isinstance(data["user_id"], int)

    @pytest_asyncio.async def test_get_current_user_unauthorized(self, client):
        """Test get current user without authentication."""
        response = await client.get("/auth/get_current_user")
        assert response.status_code == 401

    @pytest_asyncio.async def test_get_current_user_success(self, client, sample_user_data, test_db):
        """Test get current user with valid authentication."""
        # Create user and login
        await client.post("/auth/create_user", json=sample_user_data)
        
        login_data = {
            "username": sample_user_data["username"],
            "password": sample_user_data["password"]
        }
        login_response = await client.post("/auth/token", data=login_data)
        token = login_response.json()["access_token"]
        
        # Get current user
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get("/auth/get_current_user", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == sample_user_data["username"]
        assert data["role"] == sample_user_data["role"]
        assert "id" in data


class TestUserModels:
    """Tests for user models and schemas."""

    def test_create_user_request_validation(self):
        """Test CreateUserRequest schema validation."""
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "TestPass123!",
            "contact_number": "+1234567890",
            "role": "farmer"
        }
        user_request = CreateUserRequest(**user_data)
        assert user_request.username == "testuser"
        assert user_request.email == "test@example.com"
        assert user_request.role == "farmer"

    def test_user_model_creation(self):
        """Test User model creation."""
        user = Users(
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_password_here",
            contact_number="+1234567890",
            role="farmer"
        )
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.role == "farmer"


class TestUserUtilities:
    """Tests for user service utilities."""

    def test_password_hashing(self):
        """Test password hashing functionality."""
        password = "TestPass123!"
        hashed = bcrypt_context.hash(password)
        
        assert hashed != password  # Should be different
        assert bcrypt_context.verify(password, hashed)  # Should verify correctly
        assert not bcrypt_context.verify("WrongPassword", hashed)  # Should not verify wrong password

    def test_jwt_token_creation_and_validation(self):
        """Test JWT token creation and validation."""
        secret_key = os.getenv("SECRET_KEY", "test_secret")
        payload = {
            "username": "testuser",
            "id": 1,
            "role": "farmer",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=20)
        }
        
        # Create token
        token = jwt.encode(payload, secret_key, algorithm="HS256")
        
        # Decode and validate
        decoded_payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        assert decoded_payload["username"] == "testuser"
        assert decoded_payload["id"] == 1
        assert decoded_payload["role"] == "farmer"