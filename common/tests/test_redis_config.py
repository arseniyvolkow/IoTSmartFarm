import pytest
import pytest_asyncio
from unittest.mock import patch
import fakeredis.aioredis
from common.redis_config import add_token_to_blacklist, is_token_blacklisted

@pytest_asyncio.fixture(autouse=True)
async def mock_redis():
    """
    Фикстура для замены реального redis_client на fake-клиент.
    Использует pytest_asyncio.fixture для корректной обработки асинхронности.
    """
    # Создаем асинхронный fake-клиент с поддержкой decode_responses=True
    fake_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    
    # Патчим объект redis_client в модуле, где он определен
    with patch("common.redis_config.redis_client", fake_client):
        yield fake_client
    
    # Очищаем данные после каждого теста
    await fake_client.flushall()

@pytest.mark.asyncio
async def test_blacklist_flow():
    """
    Тест полного цикла: проверка отсутствия -> добавление -> подтверждение наличия.
    """
    jti = "test-token-id-123"
    expire_seconds = 60
    
    # 1. Проверяем, что изначально токена нет в блеклисте
    is_blocked_before = await is_token_blacklisted(jti)
    assert is_blocked_before is False
    
    # 2. Добавляем в блеклист
    await add_token_to_blacklist(jti, expire_seconds)
    
    # 3. Теперь токен должен быть в блеклисте
    is_blocked_after = await is_token_blacklisted(jti)
    assert is_blocked_after is True

@pytest.mark.asyncio
async def test_multiple_tokens_isolation():
    """
    Проверка, что разные токены не влияют друг на друга в Redis.
    """
    jti_1 = "token-1"
    jti_2 = "token-2"
    
    await add_token_to_blacklist(jti_1, 100)
    
    assert await is_token_blacklisted(jti_1) is True
    assert await is_token_blacklisted(jti_2) is False

@pytest.mark.asyncio
async def test_key_format_in_redis(mock_redis):
    """
    Проверка, что ключ в Redis создается с правильным префиксом 'blacklist:'.
    """
    jti = "secret-jti"
    await add_token_to_blacklist(jti, 10)
    
    # Напрямую проверяем наличие ключа в fake-клиенте
    exists = await mock_redis.exists(f"blacklist:{jti}")
    assert exists == 1