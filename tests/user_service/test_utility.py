import pytest
from datetime import timedelta, timezone, datetime
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt
import os

from user_service.models import Users
from user_service.utils import (
    authenticate_user, 
    create_access_token, 
    get_current_user,
    bcrypt_context,
    SECRET_KEY,
    ALGORITHM
)


class TestAuthenticateUser:
    """Test cases for authenticate_user function."""

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, db_session: AsyncSession):
        """Test successful user authentication."""
        # Create a user in the database
        password = "TestPassword123!"
        hashed_password = bcrypt_context.hash(password)
        
        test_user = Users(
            username="testuser",
            email="test@example.com",
            hashed_password=hashed_password,
            role="user",
            contact_number="123456789"
        )
        
        db_session.add(test_user)
        await db_session.commit()
        await db_session.refresh(test_user)
        
        # Test authentication
        result = await authenticate_user("testuser", password, db_session)
        
        assert result is not False
        assert isinstance(result, Users)
        assert result.username == "testuser"
        assert result.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_username(self, db_session: AsyncSession):
        """Test authentication with non-existent username."""
        result = await authenticate_user("nonexistent", "password123", db_session)
        assert result is False

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, db_session: AsyncSession):
        """Test authentication with wrong password."""
        # Create a user
        correct_password = "CorrectPassword123!"
        hashed_password = bcrypt_context.hash(correct_password)
        
        test_user = Users(
            username="testuser2",
            email="test2@example.com",
            hashed_password=hashed_password,
            role="user",
            contact_number="123456789"
        )
        
        db_session.add(test_user)
        await db_session.commit()
        
        # Test with wrong password
        result = await authenticate_user("testuser2", "WrongPassword123!", db_session)
        assert result is False

    @pytest.mark.asyncio
    async def test_authenticate_user_empty_password(self, db_session: AsyncSession):
        """Test authentication with empty password."""
        # Create a user
        hashed_password = bcrypt_context.hash("SomePassword123!")
        
        test_user = Users(
            username="testuser3",
            email="test3@example.com",
            hashed_password=hashed_password,
            role="user",
            contact_number="123456789"
        )
        
        db_session.add(test_user)
        await db_session.commit()
        
        # Test with empty password
        result = await authenticate_user("testuser3", "", db_session)
        assert result is False


class TestCreateAccessToken:
    """Test cases for create_access_token function."""

    def test_create_access_token_success(self):
        """Test successful token creation."""
        username = "testuser"
        user_id = 123
        role = "admin"
        expires_delta = timedelta(minutes=30)
        
        token = create_access_token(username, user_id, role, expires_delta)
        
        # Verify token is a string
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Decode and verify token content
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        assert payload["username"] == username
        assert payload["id"] == user_id
        assert payload["role"] == role
        
        # Verify expiration is set correctly (allow small time difference)
        expected_exp = datetime.now(timezone.utc) + expires_delta
        actual_exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        time_diff = abs((expected_exp - actual_exp).total_seconds())
        assert time_diff < 5  # Allow 5 seconds difference

    def test_create_access_token_different_roles(self):
        """Test token creation with different roles."""
        roles_to_test = ["user", "admin", "moderator"]
        
        for role in roles_to_test:
            token = create_access_token("testuser", 123, role, timedelta(minutes=15))
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            assert payload["role"] == role

    def test_create_access_token_different_expires_delta(self):
        """Test token creation with different expiration times."""
        short_expire = timedelta(minutes=5)
        long_expire = timedelta(hours=24)
        
        # Short expiration token
        short_token = create_access_token("user1", 1, "user", short_expire)
        short_payload = jwt.decode(short_token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Long expiration token
        long_token = create_access_token("user2", 2, "admin", long_expire)
        long_payload = jwt.decode(long_token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Verify different expiration times
        assert short_payload["exp"] < long_payload["exp"]


class TestGetCurrentUser:
    """Test cases for get_current_user function."""

    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self):
        """Test get_current_user with valid token."""
        # Create a valid token
        username = "testuser"
        user_id = 123
        role = "admin"
        token = create_access_token(username, user_id, role, timedelta(minutes=30))
        
        # Test get_current_user
        result = await get_current_user(token)
        
        assert result["username"] == username
        assert result["id"] == user_id
        assert result["role"] == role

    @pytest.mark.asyncio
    async def test_get_current_user_expired_token(self):
        """Test get_current_user with expired token."""
        # Create an expired token (negative timedelta)
        username = "testuser"
        user_id = 123
        role = "user"
        expired_token = create_access_token(
            username, user_id, role, timedelta(seconds=-1)
        )
        
        # Should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(expired_token)
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Could not validate credentials"

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self):
        """Test get_current_user with invalid token."""
        invalid_token = "invalid.token.here"
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(invalid_token)
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Could not validate credentials"

    @pytest.mark.asyncio
    async def test_get_current_user_malformed_token(self):
        """Test get_current_user with malformed but valid JWT."""
        # Create a JWT with missing required fields
        payload = {"some_field": "some_value"}  # Missing username and id
        malformed_token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(malformed_token)
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Could not validate credentials"

    @pytest.mark.asyncio
    async def test_get_current_user_token_wrong_secret(self):
        """Test get_current_user with token signed with wrong secret."""
        # Create token with different secret
        wrong_payload = {"username": "testuser", "id": 123, "role": "user"}
        wrong_token = jwt.encode(wrong_payload, "wrong_secret", algorithm=ALGORITHM)
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(wrong_token)
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Could not validate credentials"

    @pytest.mark.asyncio
    async def test_get_current_user_missing_username(self):
        """Test get_current_user with token missing username."""
        # Create token without username
        payload = {"id": 123, "role": "user", "exp": datetime.now(timezone.utc) + timedelta(minutes=30)}
        token_no_username = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token_no_username)
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Could not validate credentials"

    @pytest.mark.asyncio
    async def test_get_current_user_missing_user_id(self):
        """Test get_current_user with token missing user ID."""
        # Create token without user_id
        payload = {"username": "testuser", "role": "user", "exp": datetime.now(timezone.utc) + timedelta(minutes=30)}
        token_no_id = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token_no_id)
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Could not validate credentials"


class TestBcryptContext:
    """Test bcrypt password hashing functionality."""

    def test_password_hashing_and_verification(self):
        """Test that passwords are hashed and can be verified."""
        password = "TestPassword123!"
        
        # Hash password
        hashed = bcrypt_context.hash(password)
        
        # Verify it's actually hashed (different from original)
        assert hashed != password
        assert len(hashed) > len(password)
        assert hashed.startswith("$2b$")  # bcrypt hash prefix
        
        # Verify password verification works
        assert bcrypt_context.verify(password, hashed) is True
        assert bcrypt_context.verify("WrongPassword", hashed) is False

    def test_same_password_different_hashes(self):
        """Test that same password produces different hashes (salt)."""
        password = "SamePassword123!"
        
        hash1 = bcrypt_context.hash(password)
        hash2 = bcrypt_context.hash(password)
        
        # Different hashes due to random salt
        assert hash1 != hash2
        
        # But both should verify the same password
        assert bcrypt_context.verify(password, hash1) is True
        assert bcrypt_context.verify(password, hash2) is True


# Integration test that combines all functions
class TestAuthenticationFlow:
    """Test the complete authentication flow."""

    @pytest.mark.asyncio
    async def test_complete_auth_flow(self, db_session: AsyncSession):
        """Test complete authentication flow from user creation to token validation."""
        
        # 1. Create user with hashed password
        username = "flowtest"
        password = "FlowTest123!"
        user_id = 999
        role = "user"
        
        hashed_password = bcrypt_context.hash(password)
        test_user = Users(
            user_id=user_id,
            username=username,
            email="flowtest@example.com",
            hashed_password=hashed_password,
            role=role,
            contact_number="123456789"
        )
        
        db_session.add(test_user)
        await db_session.commit()
        
        # 2. Authenticate user
        authenticated_user = await authenticate_user(username, password, db_session)
        assert authenticated_user is not False
        assert authenticated_user.username == username
        
        # 3. Create access token
        token = create_access_token(
            authenticated_user.username, 
            authenticated_user.user_id, 
            authenticated_user.role, 
            timedelta(minutes=30)
        )
        
        # 4. Validate token
        current_user = await get_current_user(token)
        
        assert current_user["username"] == username
        assert current_user["id"] == user_id
        assert current_user["role"] == role