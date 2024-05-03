import jwt
import pytest
from fastapi import HTTPException
from datetime import datetime, timedelta
from api.auth import create_jwt_token, decode_jwt_token, get_current_user, auth, create_user
from api.config import MASTER_KEY, SECRET_KEY, TOKEN_EXPIRATION_DAYS
import sqlite3

def test_create_jwt_token():
    data = {"sub": "testuser"}
    token = create_jwt_token(data)
    assert isinstance(token, str)

def test_decode_jwt_token_valid():
    data = {"sub": "testuser"}
    token = create_jwt_token(data)
    decoded = decode_jwt_token(token)
    assert decoded["sub"] == "testuser"

def test_decode_jwt_token_expired():
    data = {"sub": "testuser"}
    token = create_jwt_token(data)
    
    # Manually set the expiration time to a past timestamp
    decoded_token = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    decoded_token["exp"] = datetime.utcnow() - timedelta(days=1)
    expired_token = jwt.encode(decoded_token, SECRET_KEY, algorithm="HS256")
    
    with pytest.raises(HTTPException) as exc_info:
        decode_jwt_token(expired_token)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Signature has expired"
    

def test_decode_jwt_token_invalid():
    token = "invalid_token"
    with pytest.raises(HTTPException) as exc_info:
        decode_jwt_token(token)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token"

@pytest.mark.asyncio
async def test_get_current_user(mocker):
    mock_credentials = mocker.Mock()
    mock_credentials.credentials = "valid_token"
    
    mock_get_db = mocker.patch("api.auth.get_db")
    mock_get_db.return_value = (mocker.Mock(), mocker.Mock())
    mock_get_db.return_value[1].fetchone.return_value = ("testuser", (datetime.utcnow() + timedelta(days=1)).isoformat())
    
    user = await get_current_user(mock_credentials)
    assert user == {"username": "testuser"}

def test_auth_valid(mocker):
    mock_get_db = mocker.patch("api.auth.get_db")
    mock_get_db.return_value = (mocker.Mock(), mocker.Mock())
    mock_get_db.return_value[1].fetchone.return_value = ("password",)
    
    result = auth("testuser", "password")
    assert "access_token" in result
    assert result["token_type"] == "bearer"

def test_auth_invalid(mocker):
    mock_get_db = mocker.patch("api.auth.get_db")
    mock_get_db.return_value = (mocker.Mock(), mocker.Mock())
    mock_get_db.return_value[1].fetchone.return_value = None
    
    with pytest.raises(HTTPException) as exc_info:
        auth("testuser", "wrongpassword")
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid username or password"

def test_create_user_valid(mocker):
    mock_get_db = mocker.patch("api.auth.get_db")
    mock_get_db.return_value = (mocker.Mock(), mocker.Mock())
    
    result = create_user("newuser", "password", MASTER_KEY)
    assert result == {"detail": "User created successfully"}

def test_create_user_invalid_master_key(mocker):
    mock_get_db = mocker.patch("api.auth.get_db")
    mock_get_db.return_value = (mocker.Mock(), mocker.Mock())
    
    with pytest.raises(HTTPException) as exc_info:
        create_user("newuser", "password", "invalid_master_key")
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Not authorized"

def test_create_user_duplicate_username(mocker):
    mock_get_db = mocker.patch("api.auth.get_db")
    mock_get_db.return_value = (mocker.Mock(), mocker.Mock())
    mock_get_db.return_value[1].execute.side_effect = sqlite3.IntegrityError
    
    with pytest.raises(HTTPException) as exc_info:
        create_user("existinguser", "password", MASTER_KEY)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Username already exists"
    