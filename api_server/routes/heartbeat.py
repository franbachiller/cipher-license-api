"""
Heartbeat route handlers for session keep-alive.

This module implements the heartbeat endpoint that allows clients to keep their
sessions alive by periodically updating the last_seen timestamp.

Requirements: 3.2, 3.3
"""

from flask import request, jsonify
import hashlib

from . import heartbeat_bp
from ..middleware.jwt_validator import require_jwt_auth
from ..database import db_pool
from ..models import Session
from ..utils.logger import get_logger

logger = get_logger(__name__)


@heartbeat_bp.route('/heartbeat', methods=['POST'])
@require_jwt_auth
def heartbeat(jwt_payload):
    """
    Update session last_seen timestamp.
    
    This endpoint allows authenticated clients to send periodic heartbeat signals
    to keep their sessions alive. The last_seen timestamp is updated in the database,
    which is used by the cleanup task to determine if a session is still active.
    
    Headers:
        Authorization: Bearer {jwt_token}
    
    Request body:
        {} (empty or minimal)
    
    Response:
        200: {"status": "alive", "next_heartbeat": 30}
        401: {"error": "Invalid or expired JWT"}
        500: {"error": "Internal server error"}
    
    Requirements: 3.2, 3.3
    """
    try:
        # Extract JWT token from Authorization header to compute hash
        auth_header = request.headers.get('Authorization')
        token = auth_header.split()[1]  # Extract token from "Bearer <token>"
        
        # Compute SHA-256 hash of JWT token
        jwt_token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # Update last_seen timestamp in database
        with db_pool.get_cursor(commit=True) as cursor:
            updated = Session.update_heartbeat(cursor, jwt_token_hash)
            
            if not updated:
                logger.warning(f"Heartbeat received for non-existent session: {jwt_token_hash[:16]}...")
                return jsonify({
                    "error": "Session not found",
                    "message": "No active session found for this token"
                }), 404
        
        # Log successful heartbeat
        license_key = jwt_payload.get('license_key', 'unknown')
        logger.debug(f"Heartbeat received for license {license_key}")
        
        # Return success response with next heartbeat interval
        return jsonify({
            "status": "alive",
            "next_heartbeat": 30
        }), 200
        
    except Exception as e:
        logger.error(f"Error processing heartbeat: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": "Failed to process heartbeat"
        }), 500
