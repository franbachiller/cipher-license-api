"""
Flask application entry point for VPS-based streaming license system.

This module initializes the Flask application with:
- Configuration management from environment variables
- Database connection pooling with psycopg2
- Blueprint registration for auth, download, heartbeat, and admin routes
- Rate limiting middleware
- Logging configuration

Usage:
    python -m api_server.app
    
    Or with gunicorn:
    gunicorn -w 4 -b 0.0.0.0:5000 api_server.app:app
"""

from flask import Flask, jsonify
import os
import sys

from .config import Config
from .database import init_db, close_db
from .routes import register_blueprints
from .middleware.rate_limiter import init_rate_limiter
from .utils.logger import setup_logging
from .utils.session_cleanup import start_cleanup_task, stop_cleanup_task


def create_app(config_override=None):
    """
    Application factory for creating Flask app instances.
    
    Args:
        config_override: Optional dictionary to override configuration values
    
    Returns:
        Configured Flask application instance
    """
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(Config)
    if config_override:
        app.config.update(config_override)
    
    # Validate configuration
    Config.validate()
    
    # Setup logging
    logger = setup_logging(app)
    logger.info("Starting VPS-based streaming license system API server")
    
    # Initialize database connection pool
    try:
        init_db()
        logger.info("Database connection pool initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        sys.exit(1)
    
    # Initialize rate limiting
    limiter = init_rate_limiter(app)
    logger.info("Rate limiting initialized")
    
    # Register blueprints
    register_blueprints(app)
    logger.info("Blueprints registered: auth, download, heartbeat, admin")
    
    # Apply rate limits to specific endpoints after blueprint registration.
    # The decorated function must replace the registered view: decorating it
    # without reassigning leaves Flask dispatching the original, unlimited view.
    endpoint_limits = {
        'auth.authenticate': "10 per minute",
        'download.download_loader': "60 per minute",
        'download.download_driver': "60 per minute",
        'download.download_cheat': "60 per minute",
        'heartbeat.heartbeat': "60 per minute",
    }
    for endpoint, limit in endpoint_limits.items():
        if endpoint in app.view_functions:
            app.view_functions[endpoint] = limiter.limit(limit)(app.view_functions[endpoint])
    
    logger.info("Rate limits applied to endpoints")
    
    # Start session cleanup background task
    try:
        start_cleanup_task(interval=300)  # Run every 5 minutes
        logger.info("Session cleanup task started")
    except Exception as e:
        logger.error(f"Failed to start session cleanup task: {e}")
        # Don't exit - cleanup is not critical for basic functionality
    
    # Health check endpoint
    @app.route('/health', methods=['GET'])
    def health_check():
        """Simple health check endpoint."""
        return jsonify({
            "status": "healthy",
            "service": "cipher-license-api",
            "version": "2.0.0"
        }), 200
    
    # Root endpoint
    @app.route('/', methods=['GET'])
    def root():
        """Root endpoint with API information."""
        return jsonify({
            "service": "Cipher License API",
            "version": "2.0.0",
            "description": "VPS-based streaming license system",
            "endpoints": {
                "auth": "/api/auth",
                "download": "/api/download/{loader|driver|cheat}",
                "heartbeat": "/api/heartbeat",
                "admin": "/admin/*"
            }
        }), 200
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Endpoint not found"}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return jsonify({"error": "Internal server error"}), 500
    
    # Cleanup on shutdown
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        """Close database connections on app context teardown."""
        if exception:
            logger.error(f"App context teardown with exception: {exception}")
    
    return app


# Create application instance
app = create_app()


if __name__ == '__main__':
    # Development server
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    print(f"Starting Flask development server on port {port}")
    print(f"Debug mode: {debug}")
    print("=" * 60)
    
    try:
        app.run(
            host='0.0.0.0',
            port=port,
            debug=debug
        )
    finally:
        # Stop cleanup task
        stop_cleanup_task()
        # Cleanup database connections
        close_db()
