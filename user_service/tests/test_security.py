import pytest
from datetime import timedelta
from fastapi import HTTPException
from user_service.security import (
    hash_password, 
    verify_password, 
    create_access_token, 
    create_refresh_token, 
    decode_access_token
)

## --- Password Hashing Tests ---

def test_password_hashing():
    password = "secure_password123"
    hashed = hash_password(password)
    
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong_password", hashed) is False

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
    data = {"sub": "test_user"}
    expires = timedelta(minutes=-1)
    token = create_access_token(data) 
    
    # Note: To test actual expiration, we'd need to manually construct 
    # a payload with an old 'exp' since create_token uses current time.
    import jwt
    from datetime import datetime, timezone
    from user_service.security import SECRET_KEY, ALGORITHM
    
    expired_payload = {
        "sub": "test",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=10)
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