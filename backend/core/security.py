"""
FIXED: JWT security with environment variables and secure fallback
"""
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status

# JWT Configuration from environment variables
# Generate a secure random secret if not provided
DEFAULT_SECRET_KEY = secrets.token_urlsafe(32)
SECRET_KEY = os.getenv("JWT_SECRET_KEY", DEFAULT_SECRET_KEY)
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "30"))

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(
    data: Dict[str, Any], 
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create JWT access token with secure defaults
    
    Args:
        data: Data to encode in the token
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    
    # Set expiration
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Add standard JWT claims
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "nbf": datetime.utcnow(),  # Not before
        "iss": "orchestraguard",  # Issuer
        "aud": "orchestraguard-api"  # Audience
    })
    
    # Encode and return
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def validate_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Validate and decode JWT token with comprehensive error handling
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded payload if valid, None if invalid
    """
    try:
        payload = jwt.decode(
            token, 
            SECRET_KEY, 
            algorithms=[ALGORITHM],
            audience="orchestraguard-api",
            issuer="orchestraguard"
        )
        return payload
    except JWTError as e:
        # Log the error (in production, use proper logging)
        print(f"JWT validation error: {e}")
        return None

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    """Generate password hash with secure defaults"""
    return pwd_context.hash(password)

def validate_interception_request(data: Dict[str, Any]) -> bool:
    """
    Validate incoming interception requests with comprehensive checks
    
    Args:
        data: Request data to validate
        
    Returns:
        True if valid, raises HTTPException if not
    """
    required_fields = ["source_agent", "target_tool", "tool_arguments"]
    
    # Check required fields
    for field in required_fields:
        if field not in data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required field: {field}"
            )
    
    # Validate field types
    if not isinstance(data.get("source_agent"), str) or not data["source_agent"].strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_agent must be a non-empty string"
        )
    
    if not isinstance(data.get("target_tool"), str) or not data["target_tool"].strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="target_tool must be a non-empty string"
        )
    
    # Validate tool_arguments
    tool_args = data.get("tool_arguments")
    if not isinstance(tool_args, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tool_arguments must be a JSON object"
        )
    
    # Ensure tool_arguments is JSON serializable
    try:
        import json
        json.dumps(tool_args)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tool_arguments must be JSON serializable"
        )
    
    # Validate user_context if provided
    user_context = data.get("user_context")
    if user_context is not None and not isinstance(user_context, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_context must be a JSON object if provided"
        )
    
    return True

def generate_api_key() -> str:
    """Generate a secure API key for service-to-service authentication"""
    return secrets.token_urlsafe(32)

def get_security_headers() -> Dict[str, str]:
    """Get security headers for API responses"""
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'"
    }