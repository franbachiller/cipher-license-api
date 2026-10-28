"""
JWT validation middleware.

This module provides a Flask decorator for validating JWT tokens on protected endpoints.
The decorator extracts the token from the Authorization header, validates its signature
and expiration, and verifies that the IP address in the token matches the request origin.

Requirements: 13.3, 13.4, 13.6
"""

from functools import wraps
from flask import request, jsonify
import jwt

# Handle both relative and absolute imports
try:
    from ..utils.jwt_utils import decode_jwt_token
except ImportError:
    from api_server.utils.jwt_utils import decode_jwt_token


def require_jwt_auth(f):
    """
    Decorator to require valid JWT token for endpoint access.
    
    This decorator validates JWT tokens by:
    1. Extracting the token from the Authorization header (Bearer format)
    2. Validating the signature and expiration using decode_jwt_token()
    3. Verifying the IP address in the token matches the request origin
    
    The decoded JWT payload is passed to the decorated function as a keyword argument 'jwt_payload'.
    
    Args:
        f: The Flask route function to decorate
    
    Returns:
        The decorated function that validates JWT before executing
    
    HTTP Response Codes:
        - 401: Missing, invalid, or expired JWT token
        - 403: IP address mismatch between token and request
        - 200: Token valid, proceeds to route handler
    
    Requirements: 13.3, 13.4, 13.6
    
    Example:
        @app.route('/api/download/loader')
        @require_jwt_auth
        def download_loader(jwt_payload):
            license_key = jwt_payload['license_key']
            # ... route logic ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Extract Authorization header
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({
                "error": "Missing Authorization header",
                "message": "Authorization header is required"
            }), 401
        
        # Check Bearer token format
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return jsonify({
                "error": "Invalid Authorization header format",
                "message": "Expected format: Bearer <token>"
            }), 401
        
        token = parts[1]
        
        # Validate JWT token signature and expiration
        try:
            payload = decode_jwt_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({
                "error": "Token expired",
                "message": "JWT token has expired, please re-authenticate"
            }), 401
        except jwt.InvalidTokenError as e:
            return jsonify({
                "error": "Invalid token",
                "message": f"JWT token validation failed: {str(e)}"
            }), 401
        except Exception as e:
            return jsonify({
                "error": "Token validation error",
                "message": f"Unexpected error during token validation: {str(e)}"
            }), 401
        
        # Verify IP address matches
        token_ip = payload.get('ip_address')
        request_ip = request.remote_addr
        
        if not token_ip:
            return jsonify({
                "error": "Invalid token",
                "message": "Token does not contain ip_address claim"
            }), 401
        
        if token_ip != request_ip:
            return jsonify({
                "error": "IP address mismatch",
                "message": f"Token IP ({token_ip}) does not match request IP ({request_ip})"
            }), 403
        
        # Token is valid, pass payload to route handler
        kwargs['jwt_payload'] = payload
        return f(*args, **kwargs)
    
    return decorated_function


# Alias for backward compatibility
require_jwt = require_jwt_auth
