import time
from unittest.mock import AsyncMock, patch

import jwt
import pytest
import redis.asyncio as redis
from fastapi import HTTPException, status

from common.auth.security import (
    ALGORITHM,
    SECRET_KEY,
    CheckAccess,
    UserIdentity,
    get_current_user_id,
    get_current_user_identity,
    get_token_payload,
    is_admin,
)


# Вспомогательная функция для создания токенов для тестирования
def create_test_token(payload: dict):
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


@pytest.mark.asyncio
async def test_get_token_payload_success():
    payload = {"sub": "user_1", "jti": "unique_jti", "exp": 9999999999}
    token = create_test_token(payload)

    with patch(
        "common.auth.security.redis_client", new_callable=AsyncMock
    ) as mock_redis:
        mock_redis.get.return_value = None  # Cache miss
        with patch(
            "common.auth.security.is_token_blacklisted", new_callable=AsyncMock
        ) as mock_blacklist:
            mock_blacklist.return_value = False

            result = await get_token_payload(token)

            assert result["sub"] == "user_1"
            mock_blacklist.assert_called_once_with("unique_jti")


@pytest.mark.asyncio
async def test_get_token_payload_blacklisted():
    payload = {"sub": "user_1", "jti": "revoked_jti"}
    token = create_test_token(payload)

    with patch(
        "common.auth.security.redis_client", new_callable=AsyncMock
    ) as mock_redis:
        mock_redis.get.return_value = None  # Cache miss
        with patch(
            "common.auth.security.is_token_blacklisted", new_callable=AsyncMock
        ) as mock_blacklist:
            mock_blacklist.return_value = True

            with pytest.raises(HTTPException) as exc:
                await get_token_payload(token)

            assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "revoked" in exc.value.detail


@pytest.mark.asyncio
async def test_get_token_payload_invalid_token():
    # Тест на передачу некорректной строки вместо токена
    with patch(
        "common.auth.security.redis_client", new_callable=AsyncMock
    ) as mock_redis:
        mock_redis.get.return_value = None  # Cache miss
        with pytest.raises(HTTPException) as exc:
            await get_token_payload("invalid-token-string")

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Could not validate credentials" in exc.value.detail


@pytest.mark.asyncio
async def test_get_token_payload_redis_error():
    token = create_test_token({"sub": "user_1", "jti": "some_jti"})

    with patch(
        "common.auth.security.redis_client", new_callable=AsyncMock
    ) as mock_redis:
        mock_redis.get.side_effect = redis.RedisError
        with patch(
            "common.auth.security.is_token_blacklisted", side_effect=redis.RedisError
        ):
            with pytest.raises(HTTPException) as exc:
                await get_token_payload(token)

            assert exc.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


@pytest.mark.asyncio
async def test_get_current_user_identity():
    payload = {
        "sub": "user_123",
        "email": "test@example.com",
        "role": "admin",
        "g_perms": {"r_all": True},
        "access": {"farms": {"r": True}},
        "exp": time.time() + 300,
    }
    token = create_test_token(payload)

    with patch(
        "common.auth.security.redis_client", new_callable=AsyncMock
    ) as mock_redis:
        mock_redis.get.return_value = None  # Cache miss

        user = await get_current_user_identity(token)

        assert isinstance(user, UserIdentity)
        assert user.id == "user_123"
        assert user.email == "test@example.com"
        assert user.role == "admin"
        assert user.raw_payload["sub"] == payload["sub"]


def test_helpers():
    # Тест хелпера is_admin
    assert is_admin({"g_perms": {"w_all": True}}) is True
    assert is_admin({"g_perms": {"w_all": False}}) is False
    assert is_admin({}) is False

    # Тест хелпера get_current_user_id
    assert get_current_user_id({"sub": "123"}) == "123"
    assert get_current_user_id({}) is None


class TestCheckAccess:
    @pytest.mark.asyncio
    async def test_global_write_access(self):
        # Пользователь с глобальными правами (w_all: True) должен проходить любую проверку записи
        checker = CheckAccess(resource="sensors", action="write")
        user = UserIdentity({"g_perms": {"w_all": True}})

        result = await checker(user)
        assert result == user

    @pytest.mark.asyncio
    async def test_resource_specific_access_success(self):
        # Проверка прав на чтение конкретного ресурса
        checker = CheckAccess(resource="farms", action="read")
        user = UserIdentity({"g_perms": {}, "access": {"farms": {"r": True}}})

        result = await checker(user)
        assert result == user

    @pytest.mark.asyncio
    async def test_resource_specific_access_denied(self):
        # Ошибка, если ресурса нет в списке разрешенных
        checker = CheckAccess(resource="sensors", action="read")
        user = UserIdentity({"access": {"farms": {"r": True}}})

        with pytest.raises(HTTPException) as exc:
            await checker(user)
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_insufficient_permission_level(self):
        # Ошибка, если ресурс есть, но конкретное действие (delete) запрещено
        checker = CheckAccess(resource="farms", action="delete")
        user = UserIdentity({"access": {"farms": {"r": True, "w": True, "d": False}}})

        with pytest.raises(HTTPException) as exc:
            await checker(user)
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN
