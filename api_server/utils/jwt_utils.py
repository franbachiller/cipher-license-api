"""
JWT token generation and validation utilities.

This module provides functions for creating and validating JWT tokens
for the VPS-based streaming license system.
"""

import jwt
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

# Handle both relative and absolute imports
try:
    from ..config import Config
except ImportError:
    from config import Config


def generate_jwt_token(license_key: str, ip_address: str) -> str:
    """
    Generate a JWT token with HS256 signing.
    
    Creates a JWT token with the following structure:
    - Header: {"alg": "HS256", "typ": "JWT"}
    - Payload: {"license_key": "...", "ip_address": "...", "iat": timestamp, "exp": timestamp}
    - Signature: HMACSHA256(base64UrlEncode(header) + "." + base64UrlEncode(payload), secret_key)
    
    Args:
        license_key: The license key to include in the token
        ip_address: The client IP address to include in the token
    
    Returns:
        str: The encoded JWT token
    
    Requirements: 1.2, 13.1, 13.2
    """
    current_time = datetime.now(timezone.utc)
    expiration_time = current_time + timedelta(minutes=Config.JWT_EXPIRATION_MINUTES)
    
    payload = {
        'license_key': license_key,
        'ip_address': ip_address,
        'iat': int(current_time.timestamp()),
        'exp': int(expiration_time.timestamp())
    }
    
    token = jwt.encode(
        payload,
        Config.JWT_SECRET_KEY,
        algorithm='HS256'
    )
    
    return token


def decode_jwt_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT token.
    
    Validates the token signature and expiration. Does not verify IP address
    (that should be done separately by the caller).
    
    Args:
        token: The JWT token to decode
    
    Returns:
        Dict[str, Any]: The decoded token payload containing license_key, ip_address, iat, exp
    
    Raises:
        jwt.ExpiredSignatureError: If the token has expired
        jwt.InvalidTokenError: If the token is invalid or signature verification fails
    
    Requirements: 13.3, 13.4
    """
    payload = jwt.decode(
        token,
        Config.JWT_SECRET_KEY,
        algorithms=['HS256']
    )
    
    return payload
