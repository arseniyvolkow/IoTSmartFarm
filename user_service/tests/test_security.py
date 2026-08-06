from datetime import timedelta

import pytest
from fastapi import HTTPException

from common.auth.security import decode_access_token
from user_service.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)

## --- Password Hashing Tests ---


@pytest.mark.asyncio
async def test_password_hashing():
    password = "secure_password123"
    hashed = await hash_password(password)

    assert hashed != password
    assert await verify_password(password, hashed) is True
    assert await verify_password("wrong_password", hashed) is False


## --- Token Creation Tests ---


def test_create_access_token():
    data = {"sub": "user_123", "role": "admin"}
    token = create_access_token(data)

    assert isinstance(token, str)

    # Decode to verify contents
    payload = decode_access_token(token)
    assert payload["sub"] == "user_123"
    assert payload["type"] == "access"
    assert "exp" in payload
    assert "jti" in payload


def test_create_refresh_token():
    data = {"sub": "user_123"}
    token = create_refresh_token(data)

    payload = decode_access_token(token)
    assert payload["type"] == "refresh"


## --- Token Validation & Security Tests ---


def test_decode_expired_token():
    # Create a token that expired 1 minute ago

    # Note: To test actual expiration, we'd need to manually construct
    # a payload with an old 'exp' since create_token uses current time.
    from datetime import datetime, timezone

    import jwt

    from user_service.security import ALGORITHM, SECRET_KEY

    expired_payload = {
        "sub": "test",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=10),
    }
    expired_token = jwt.encode(expired_payload, SECRET_KEY, algorithm=ALGORITHM)

    with pytest.raises(HTTPException) as exc:
        decode_access_token(expired_token)
    assert exc.value.status_code == 401
    assert "expired" in exc.value.detail.lower()


def test_decode_invalid_token():
    with pytest.raises(HTTPException) as exc:
        decode_access_token("not-a-real-token-at-all")
    assert exc.value.status_code == 401
