"""
Route blueprints for the VPS-based streaming license system.
"""

from flask import Blueprint

# Create blueprints for different route groups
auth_bp = Blueprint('auth', __name__, url_prefix='/api')
download_bp = Blueprint('download', __name__, url_prefix='/api/download')
heartbeat_bp = Blueprint('heartbeat', __name__, url_prefix='/api')
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def register_blueprints(app):
    """
    Register all blueprints with the Flask application.
    
    Args:
        app: Flask application instance
    """
    # Import route modules to register routes with blueprints
    from . import auth, download, heartbeat, admin
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(download_bp)
    app.register_blueprint(heartbeat_bp)
    app.register_blueprint(admin_bp)
