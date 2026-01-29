"""
JWT & Request Validation Security Module
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create JWT access token."""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def validate_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """Validate and decode JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash."""
    return pwd_context.hash(password)


def validate_interception_request(data: Dict[str, Any]) -> bool:
    """
    Validate incoming interception requests.
    Returns True if valid, raises HTTPException if not.
    """
    required_fields = ["source_agent", "target_tool", "tool_arguments"]

    for field in required_fields:
        if field not in data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required field: {field}",
            )

    # Validate tool_arguments is a dict
    if not isinstance(data.get("tool_arguments"), dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tool_arguments must be a JSON object",
        )

    # Validate target_tool format (basic)
    target_tool = data.get("target_tool", "")
    if not target_tool or not isinstance(target_tool, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="target_tool must be a non-empty string",
        )

    return True