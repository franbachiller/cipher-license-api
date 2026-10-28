"""
Rate limiting configuration using Flask-Limiter.

Implements rate limiting for API endpoints:
- /api/auth: 10 requests per minute per IP
- Other /api/* endpoints: 60 requests per minute per IP

Requirements: 5.2
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import jsonify


def init_rate_limiter(app):
    """
    Initialize Flask-Limiter with the application.
    
    Configures rate limiting based on IP address:
    - Authentication endpoint: 10 requests/minute
    - Other API endpoints: 60 requests/minute
    
    Args:
        app: Flask application instance
    
    Returns:
        Limiter instance
    """
    # Initialize limiter with memory storage
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=[],
        storage_uri="memory://"
    )
    
    # Custom error handler for 429 responses
    @app.errorhandler(429)
    def ratelimit_handler(e):
        """
        Handle rate limit exceeded errors.
        
        Returns:
            JSON response with error message and 429 status code
        """
        return jsonify({
            "error": "Rate limit exceeded",
            "message": str(e.description)
        }), 429
    
    return limiter
