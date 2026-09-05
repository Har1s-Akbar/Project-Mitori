import os
import pytest
import jwt
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

TEST_SECRET = "ci-test-shared-jwt-secret"
os.environ["JWT_SECRET_KEY"] = TEST_SECRET
os.environ["ALGORITHM"] = "HS256"

from api.security import is_user_Authenticated

def generate_mock_django_token(
    user_id: str = "user-12345", 
    kyc_verified: bool = True or None, 
    expires_in_minutes: int = 15,
    secret: str = TEST_SECRET
) -> str:
    """
    Mimics the exact payload structure output by Django's simplejwt.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "token_type": "access",
        "exp": now + timedelta(minutes=expires_in_minutes),
        "iat": now,
        "jti": "mock_jti_string",
        "user_id": user_id,
        "is_kyc_verified": kyc_verified  
    }
    return jwt.encode(payload, secret, algorithm="HS256")

@pytest.mark.asyncio
async def test_jwt_kyc_false():
    valid_token = generate_mock_django_token(kyc_verified=False)
    mock_credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=valid_token)

    with pytest.raises(HTTPException) as exep_info:
        await is_user_Authenticated(mock_credentials)
    assert exep_info.value.status_code == 403
    assert "Kyc not completed : can not trade" in exep_info.value.detail


@pytest.mark.asyncio
async def test_kyc_none():
    valid_token = generate_mock_django_token(kyc_verified=None)

    mock_credentials = HTTPAuthorizationCredentials(scheme="bearer", credentials=valid_token)

    with pytest.raises(HTTPException) as exep_info:
        await is_user_Authenticated(mock_credentials)

    assert exep_info.value.status_code == 403
    assert "Kyc not completed : can not trade" in exep_info.value.detail

@pytest.mark.asyncio
async def test_valid_token_authorizes_user():
    """
    Happy Path: Proves a valid simplejwt token is correctly decrypted 
    and returns the authorized user data.
    """
    valid_token = generate_mock_django_token()
    mock_credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=valid_token)
    
    user_data = await is_user_Authenticated(mock_credentials)
    
    assert user_data is not None
    assert user_data.user_id == "user-12345"
    assert user_data.kyc_verified is True

@pytest.mark.asyncio
async def test_expired_token_raises_401():
    """
    Time-To-Live Boundary: Proves that tokens past their 'exp' claim are rejected with 401.
    """
    expired_token = generate_mock_django_token(expires_in_minutes=-5)
    mock_credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=expired_token)
    
    with pytest.raises(HTTPException) as exc_info:
        await is_user_Authenticated(mock_credentials)
        
    assert exc_info.value.status_code == 401

@pytest.mark.asyncio
async def test_invalid_signature_raises_401():
    """
    Cryptographic Boundary: Proves that tokens signed with a different secret are rejected.
    """
    forged_token = generate_mock_django_token(secret="3d8ea09e7fa438c9eeeb0bff1abd281313b219703ad3c79ea64c96b8c464fb09")
    mock_credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=forged_token)
    
    with pytest.raises(HTTPException) as exc_info:
        await is_user_Authenticated(mock_credentials)
        
    assert exc_info.value.status_code == 403 # Your code maps general invalid tokens to 403

@pytest.mark.asyncio
async def test_missing_user_id_claim_raises_401():
    """
    Payload Integrity Boundary: Proves that a token missing user_id is rejected.
    """
    now = datetime.now(timezone.utc)
    malformed_payload = {
        "token_type": "access",
        "exp": now + timedelta(minutes=15),
        "is_kyc_verified": True
    }
    malformed_token = jwt.encode(malformed_payload, TEST_SECRET, algorithm="HS256")
    mock_credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=malformed_token)
    
    with pytest.raises(HTTPException) as exc_info:
        await is_user_Authenticated(mock_credentials)
        
    assert exc_info.value.status_code == 401