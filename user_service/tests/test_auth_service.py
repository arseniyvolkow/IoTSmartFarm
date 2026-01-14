import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from fastapi import HTTPException
from user_service.schemas import UserLogin, TokenPair

# Вспомогательные классы оставляем здесь, так как они нужны для генерации Payload
class MockUser:
    def __init__(self, id, email, hashed_password, role=None):
        self.id = id
        self.email = email
        self.hashed_password = hashed_password
        self.role = role

class MockRole:
    def __init__(self, name, can_read_all=False, can_write_all=False, access_list=None):
        self.name = name
        self.can_read_all = can_read_all
        self.can_write_all = can_write_all
        self.access_list = access_list or []

class MockAccess:
    def __init__(self, resource, r=False, w=False, d=False):
        self.resource = resource
        self.can_read = r
        self.can_write = w
        self.can_delete = d

# Фикстуры db_session и auth_service теперь приходят из conftest.py автоматически

@pytest.mark.asyncio
async def test_create_payload_logic(auth_service):
    """Проверка логики формирования JWT payload (использует фикстуру из conftest)."""
    access = [MockAccess("farms", r=True, w=False, d=False)]
    role = MockRole("operator", can_read_all=True, access_list=access)
    user = MockUser(id=1, email="test@test.com", hashed_password="...", role=role)
    
    payload = auth_service._create_payload(user)
    
    assert payload["sub"] == "1"
    assert payload["role"] == "operator"

@pytest.mark.asyncio
@patch("user_service.services.auth_service.verify_password")
@patch("user_service.services.auth_service.create_access_token")
@patch("user_service.services.auth_service.create_refresh_token")
async def test_login_user_success(
    mock_refresh, mock_access, mock_verify, auth_service, db_session
):
    """Успешный вход. Здесь db_session — это реальный AsyncMock (если мы патчим execute) 
    или реальный SQLite (если не патчим). Для Unit-теста пропатчим execute."""
    mock_verify.return_value = True
    mock_access.return_value = "fake_access"
    mock_refresh.return_value = "fake_refresh"
    
    # Имитируем поведение БД
    user = MockUser(id=1, email="test@test.com", hashed_password="hash")
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    
    with patch.object(db_session, 'execute', return_value=mock_result):
        login_info = UserLogin(email="test@test.com", password="password123")
        tokens = await auth_service.login_user(login_info)
        
        assert tokens.access_token == "fake_access"
        mock_verify.assert_called_once()

@pytest.mark.asyncio
@patch("user_service.services.auth_service.decode_access_token")
@patch("user_service.services.auth_service.is_token_blacklisted", new_callable=AsyncMock)
@patch("user_service.services.auth_service.add_token_to_blacklist", new_callable=AsyncMock)
@patch("user_service.services.auth_service.create_access_token")
@patch("user_service.services.auth_service.create_refresh_token")
async def test_refresh_token_success(
    mock_create_refresh, 
    mock_create_access, 
    mock_add_blacklist, 
    mock_is_blacklisted, 
    mock_decode, 
    auth_service, 
    db_session
):
    """Обновление токена. Используем общие фикстуры."""
    now = datetime.now(timezone.utc).timestamp()
    mock_decode.return_value = {
        "sub": "1", "jti": "old_jti", "type": "refresh", "exp": now + 300
    }
    mock_is_blacklisted.return_value = False
    mock_create_access.return_value = "new_access"
    mock_create_refresh.return_value = "new_refresh"
    
    user = MockUser(id=1, email="test@test.com", hashed_password="...")
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    
    with patch.object(db_session, 'execute', return_value=mock_result):
        result = await auth_service.refresh_access_token("old_refresh")
        assert result.access_token == "new_access"