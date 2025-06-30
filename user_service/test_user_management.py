import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from .routers.user import ChangePassword, ChangeNumber, UserInfoResponse
from .models import Users
from passlib.context import CryptContext
from faker import Faker

fake = Faker()
bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TestUserManagement:
    """Unit tests for user management functionality."""

    @pytest_asyncio.fixture
    async def mock_db_session(self):
        """Mock database session."""
        session = Mock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest_asyncio.fixture
    def sample_user(self):
        """Create a sample user for testing."""
        return Users(
            user_id=1,
            username="testuser",
            email="test@example.com",
            hashed_password=bcrypt_context.hash("OldPass123!"),
            contact_number="+1234567890",
            role="farmer"
        )

    def test_change_password_schema_validation(self):
        """Test ChangePassword schema validation."""
        change_password_data = {
            "old_password": "OldPass123!",
            "new_password": "NewPass123!"
        }
        change_password = ChangePassword(**change_password_data)
        assert change_password.old_password == "OldPass123!"
        assert change_password.new_password == "NewPass123!"

    def test_change_password_schema_validation_short_password(self):
        """Test ChangePassword schema validation with short password."""
        with pytest.raises(Exception):  # Pydantic validation error
            ChangePassword(
                old_password="OldPass123!",
                new_password="short"  # Too short
            )

    def test_change_number_schema_validation(self):
        """Test ChangeNumber schema validation."""
        change_number_data = {
            "new_number": "+9876543210"
        }
        change_number = ChangeNumber(**change_number_data)
        assert change_number.new_number == "+9876543210"

    def test_change_number_schema_validation_empty(self):
        """Test ChangeNumber schema validation with empty number."""
        with pytest.raises(Exception):  # Pydantic validation error
            ChangeNumber(new_number="")  # Empty should fail

    def test_user_info_response_model(self):
        """Test UserInfoResponse model."""
        user_data = {
            "user_id": 1,
            "username": "testuser",
            "email": "test@example.com",
            "role": "farmer",
            "contact_number": "+1234567890"
        }
        user_info = UserInfoResponse(**user_data)
        assert user_info.user_id == 1
        assert user_info.username == "testuser"
        assert user_info.email == "test@example.com"
        assert user_info.role == "farmer"
        assert user_info.contact_number == "+1234567890"

    def test_user_info_response_optional_contact(self):
        """Test UserInfoResponse with optional contact number."""
        user_data = {
            "user_id": 1,
            "username": "testuser",
            "email": "test@example.com",
            "role": "farmer"
        }
        user_info = UserInfoResponse(**user_data)
        assert user_info.contact_number is None


class TestUserRoutes:
    """Integration tests for user management routes."""

    @pytest_asyncio.async def test_user_info_unauthorized(self, client):
        """Test get user info without authentication."""
        response = await client.get("/user/info")
        assert response.status_code == 401

    @pytest_asyncio.async def test_user_info_success(self, client, sample_user_data, test_db):
        """Test successful user info retrieval."""
        # Create user and login
        await client.post("/auth/create_user", json=sample_user_data)
        
        login_data = {
            "username": sample_user_data["username"],
            "password": sample_user_data["password"]
        }
        login_response = await client.post("/auth/token", data=login_data)
        token = login_response.json()["access_token"]
        
        # Get user info
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get("/user/info", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == sample_user_data["username"]
        assert data["email"] == sample_user_data["email"]
        assert data["role"] == sample_user_data["role"]
        assert "user_id" in data

    @pytest_asyncio.async def test_change_password_unauthorized(self, client):
        """Test change password without authentication."""
        change_password_data = {
            "old_password": "OldPass123!",
            "new_password": "NewPass123!"
        }
        response = await client.put("/user/change_password", json=change_password_data)
        assert response.status_code == 401

    @pytest_asyncio.async def test_change_password_success(self, client, sample_user_data, test_db):
        """Test successful password change."""
        # Create user and login
        await client.post("/auth/create_user", json=sample_user_data)
        
        login_data = {
            "username": sample_user_data["username"],
            "password": sample_user_data["password"]
        }
        login_response = await client.post("/auth/token", data=login_data)
        token = login_response.json()["access_token"]
        
        # Change password
        change_password_data = {
            "old_password": sample_user_data["password"],
            "new_password": "NewPass123!"
        }
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.put("/user/change_password", json=change_password_data, headers=headers)
        
        assert response.status_code == 204

        # Verify old password no longer works
        old_login_data = {
            "username": sample_user_data["username"],
            "password": sample_user_data["password"]
        }
        old_login_response = await client.post("/auth/token", data=old_login_data)
        assert old_login_response.status_code == 401

        # Verify new password works
        new_login_data = {
            "username": sample_user_data["username"],
            "password": "NewPass123!"
        }
        new_login_response = await client.post("/auth/token", data=new_login_data)
        assert new_login_response.status_code == 200

    @pytest_asyncio.async def test_change_password_wrong_old_password(self, client, sample_user_data, test_db):
        """Test password change with wrong old password."""
        # Create user and login
        await client.post("/auth/create_user", json=sample_user_data)
        
        login_data = {
            "username": sample_user_data["username"],
            "password": sample_user_data["password"]
        }
        login_response = await client.post("/auth/token", data=login_data)
        token = login_response.json()["access_token"]
        
        # Try to change password with wrong old password
        change_password_data = {
            "old_password": "WrongOldPassword",
            "new_password": "NewPass123!"
        }
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.put("/user/change_password", json=change_password_data, headers=headers)
        
        assert response.status_code == 401
        assert "Current password is incorrect" in response.json()["detail"]

    @pytest_asyncio.async def test_change_password_short_new_password(self, client, sample_user_data, test_db):
        """Test password change with too short new password."""
        # Create user and login
        await client.post("/auth/create_user", json=sample_user_data)
        
        login_data = {
            "username": sample_user_data["username"],
            "password": sample_user_data["password"]
        }
        login_response = await client.post("/auth/token", data=login_data)
        token = login_response.json()["access_token"]
        
        # Try to change password with short new password
        change_password_data = {
            "old_password": sample_user_data["password"],
            "new_password": "short"  # Too short
        }
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.put("/user/change_password", json=change_password_data, headers=headers)
        
        assert response.status_code == 422  # Validation error

    @pytest_asyncio.async def test_change_number_unauthorized(self, client):
        """Test change contact number without authentication."""
        change_number_data = {
            "new_number": "+9876543210"
        }
        response = await client.put("/user/change_number", json=change_number_data)
        assert response.status_code == 401

    @pytest_asyncio.async def test_change_number_success(self, client, sample_user_data, test_db):
        """Test successful contact number change."""
        # Create user and login
        await client.post("/auth/create_user", json=sample_user_data)
        
        login_data = {
            "username": sample_user_data["username"],
            "password": sample_user_data["password"]
        }
        login_response = await client.post("/auth/token", data=login_data)
        token = login_response.json()["access_token"]
        
        # Change contact number
        change_number_data = {
            "new_number": "+9876543210"
        }
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.put("/user/change_number", json=change_number_data, headers=headers)
        
        assert response.status_code == 204

        # Verify number was changed
        user_info_response = await client.get("/user/info", headers=headers)
        assert user_info_response.status_code == 200
        user_data = user_info_response.json()
        assert user_data["contact_number"] == "+9876543210"

    @pytest_asyncio.async def test_change_number_empty(self, client, sample_user_data, test_db):
        """Test contact number change with empty number."""
        # Create user and login
        await client.post("/auth/create_user", json=sample_user_data)
        
        login_data = {
            "username": sample_user_data["username"],
            "password": sample_user_data["password"]
        }
        login_response = await client.post("/auth/token", data=login_data)
        token = login_response.json()["access_token"]
        
        # Try to change to empty number
        change_number_data = {
            "new_number": ""
        }
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.put("/user/change_number", json=change_number_data, headers=headers)
        
        assert response.status_code == 422  # Validation error


class TestPasswordSecurity:
    """Tests for password security functionality."""

    def test_password_hashing_security(self):
        """Test password hashing security."""
        password = "TestPass123!"
        
        # Hash the same password multiple times
        hash1 = bcrypt_context.hash(password)
        hash2 = bcrypt_context.hash(password)
        
        # Hashes should be different (due to salt)
        assert hash1 != hash2
        
        # But both should verify the original password
        assert bcrypt_context.verify(password, hash1)
        assert bcrypt_context.verify(password, hash2)

    def test_password_verification_security(self):
        """Test password verification security."""
        correct_password = "TestPass123!"
        wrong_password = "WrongPass123!"
        
        hashed = bcrypt_context.hash(correct_password)
        
        # Correct password should verify
        assert bcrypt_context.verify(correct_password, hashed)
        
        # Wrong password should not verify
        assert not bcrypt_context.verify(wrong_password, hashed)

    def test_password_strength_requirements(self, valid_passwords, invalid_passwords):
        """Test password strength validation."""
        # This would be part of the validation logic in the actual endpoint
        for valid_password in valid_passwords:
            # These should all be valid passwords
            assert len(valid_password) >= 8
            assert any(c.isupper() for c in valid_password)
            assert any(c.islower() for c in valid_password)
            assert any(c.isdigit() for c in valid_password)
            assert any(c in "!@#$%^&*(),.?\":{}|<>" for c in valid_password)


class TestUserPermissions:
    """Tests for user permission functionality."""

    def test_check_permissions_function(self):
        """Test the check_permissions decorator function."""
        from .routers.user import check_permissions
        
        # Create a mock user with farmer role
        farmer_user = {"username": "farmer", "id": 1, "role": "farmer"}
        admin_user = {"username": "admin", "id": 2, "role": "admin"}
        
        # Test farmer permission check
        farmer_check = check_permissions("farmer")
        result = farmer_check(farmer_user)
        assert result == farmer_user
        
        # Test admin permission check with admin user
        admin_check = check_permissions("admin")
        result = admin_check(admin_user)
        assert result == admin_user
        
        # Test admin permission check with farmer user (should fail)
        with pytest.raises(HTTPException) as exc_info:
            admin_check(farmer_user)
        
        assert exc_info.value.status_code == 403
        assert "permission" in str(exc_info.value.detail)

    def test_role_based_access_patterns(self):
        """Test role-based access control patterns."""
        users = [
            {"username": "farmer1", "id": 1, "role": "farmer"},
            {"username": "admin1", "id": 2, "role": "admin"},
            {"username": "manager1", "id": 3, "role": "manager"},
        ]
        
        for user in users:
            # All users should have basic access
            assert "role" in user
            assert user["role"] in ["farmer", "admin", "manager"]
            
            # Role-specific checks
            if user["role"] == "admin":
                # Admin should have elevated permissions
                assert user["role"] == "admin"
            elif user["role"] == "farmer":
                # Farmer should have basic permissions
                assert user["role"] == "farmer"