"""
Admin route handlers for license management.

This module provides administrative endpoints for managing licenses and sessions.
These endpoints should be protected with admin authentication in production.

Requirements: 4.1, 4.3, 4.4, 4.5, 4.6, 10.4, 10.5, 10.6
"""

from flask import request, jsonify
from datetime import datetime
from . import admin_bp
from ..database import db_pool
from ..models import License, Session
from ..middleware.admin_auth import require_admin_auth
from ..utils.logger import get_logger

logger = get_logger(__name__)


@admin_bp.route('/license/create', methods=['POST'])
@require_admin_auth
def create_license():
    """
    Create a new license key.
    
    This endpoint generates a unique license key and creates a new license
    record with the specified parameters.
    
    Headers:
        Authorization: Bearer {admin_token}
    
    Request body:
        {
            "expires_at": "2024-12-31T23:59:59Z",
            "max_sessions": 1,
            "note": "Customer #12345"
        }
    
    Response:
        200: {"license_key": "...", "status": "active", ...}
        400: {"error": "Invalid request format"}
        500: {"error": "Internal server error"}
    
    Requirements: 4.1, 10.4
    """
    try:
        # Parse request body
        data = request.get_json()
        
        if not data or 'expires_at' not in data:
            return jsonify({
                "error": "Invalid request format",
                "message": "expires_at is required"
            }), 400
        
        # Parse expires_at timestamp
        try:
            expires_at = datetime.fromisoformat(data['expires_at'].replace('Z', '+00:00'))
        except (ValueError, AttributeError) as e:
            return jsonify({
                "error": "Invalid expires_at format",
                "message": "expires_at must be in ISO 8601 format (e.g., 2024-12-31T23:59:59Z)"
            }), 400
        
        # Get optional parameters
        max_sessions = data.get('max_sessions', 1)
        note = data.get('note', '')
        
        # Validate max_sessions
        if not isinstance(max_sessions, int) or max_sessions < 1:
            return jsonify({
                "error": "Invalid max_sessions",
                "message": "max_sessions must be an integer >= 1"
            }), 400
        
        # Import license service
        from ..utils.license_service import create_license as create_license_service
        
        # Create license
        license_data = create_license_service(expires_at, max_sessions, note)
        
        logger.info(f"License created: {license_data['license_key']}")
        
        return jsonify(license_data), 200
        
    except ValueError as e:
        logger.error(f"Validation error creating license: {e}")
        return jsonify({
            "error": "Validation error",
            "message": str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error creating license: {e}", exc_info=True)
        return jsonify({
            "error": "Internal server error",
            "message": "Failed to create license"
        }), 500


@admin_bp.route('/license/revoke', methods=['POST'])
@require_admin_auth
def revoke_license():
    """
    Revoke a license and terminate its sessions.
    
    This endpoint updates the license status to "revoked" and immediately
    terminates all active sessions associated with that license key.
    
    Headers:
        Authorization: Bearer {admin_token}
    
    Request body:
        {
            "license_key": "ABCD1234EFGH5678IJKL90MNO"
        }
    
    Response:
        200: {"message": "License revoked", "sessions_terminated": 2}
        400: {"error": "Invalid request format"}
        404: {"error": "License not found"}
        500: {"error": "Internal server error"}
    
    Requirements: 4.3, 4.4
    """
    try:
        # Parse request body
        data = request.get_json()
        
        if not data or 'license_key' not in data:
            return jsonify({
                "error": "Invalid request format",
                "message": "license_key is required"
            }), 400
        
        license_key = data['license_key']
        
        # Validate license key format
        if not license_key or len(license_key) != 25:
            return jsonify({
                "error": "Invalid license key format",
                "message": "License key must be 25 characters"
            }), 400
        
        with db_pool.get_cursor(commit=True) as cursor:
            # Check if license exists
            license_obj = License.find_by_key(cursor, license_key)
            
            if not license_obj:
                return jsonify({
                    "error": "License not found",
                    "message": f"No license found with key: {license_key}"
                }), 404
            
            # Update license status to revoked
            License.update_status(cursor, license_key, 'revoked')
            
            # Terminate all active sessions for this license
            sessions_terminated = Session.delete_by_license_key(cursor, license_key)
            
            logger.info(f"License revoked: {license_key}, terminated {sessions_terminated} session(s)")
        
        return jsonify({
            "message": "License revoked successfully",
            "license_key": license_key,
            "sessions_terminated": sessions_terminated
        }), 200
        
    except Exception as e:
        logger.error(f"Error revoking license: {e}", exc_info=True)
        return jsonify({
            "error": "Internal server error",
            "message": "Failed to revoke license"
        }), 500


@admin_bp.route('/license/extend', methods=['POST'])
@require_admin_auth
def extend_license():
    """
    Extend license expiration date.
    
    This endpoint updates the expiration date for an existing license.
    It can be used to extend expired licenses or modify active license durations.
    
    Headers:
        Authorization: Bearer {admin_token}
    
    Request body:
        {
            "license_key": "ABCD1234EFGH5678IJKL90MNO",
            "new_expires_at": "2025-12-31T23:59:59Z"
        }
    
    Response:
        200: {"message": "License extended", "expires_at": "..."}
        400: {"error": "Invalid request format"}
        404: {"error": "License not found"}
        500: {"error": "Internal server error"}
    
    Requirements: 4.5
    """
    try:
        # Parse request body
        data = request.get_json()
        
        if not data or 'license_key' not in data or 'new_expires_at' not in data:
            return jsonify({
                "error": "Invalid request format",
                "message": "license_key and new_expires_at are required"
            }), 400
        
        license_key = data['license_key']
        
        # Validate license key format
        if not license_key or len(license_key) != 25:
            return jsonify({
                "error": "Invalid license key format",
                "message": "License key must be 25 characters"
            }), 400
        
        # Parse new_expires_at timestamp
        try:
            new_expires_at = datetime.fromisoformat(data['new_expires_at'].replace('Z', '+00:00'))
        except (ValueError, AttributeError) as e:
            return jsonify({
                "error": "Invalid new_expires_at format",
                "message": "new_expires_at must be in ISO 8601 format (e.g., 2025-12-31T23:59:59Z)"
            }), 400
        
        # Import license service
        from ..utils.license_service import extend_license as extend_license_service
        
        # Extend license
        result = extend_license_service(license_key, new_expires_at)
        
        logger.info(f"License extended: {license_key}, new expiry: {result['expires_at']}")
        
        return jsonify(result), 200
        
    except ValueError as e:
        # License not found
        logger.warning(f"License not found for extension: {str(e)}")
        return jsonify({
            "error": "License not found",
            "message": str(e)
        }), 404
    except Exception as e:
        logger.error(f"Error extending license: {e}", exc_info=True)
        return jsonify({
            "error": "Internal server error",
            "message": "Failed to extend license"
        }), 500


@admin_bp.route('/licenses', methods=['GET'])
@require_admin_auth
def list_licenses():
    """
    List all licenses with optional filtering.
    
    This endpoint retrieves licenses with optional status filtering and pagination.
    For each license, it also includes the count of active sessions.
    
    Headers:
        Authorization: Bearer {admin_token}
    
    Query parameters:
        status: active|expired|revoked (optional)
        limit: integer (default 100)
        offset: integer (default 0)
    
    Response:
        200: {"licenses": [...], "total": 150, "limit": 100, "offset": 0}
        400: {"error": "Invalid parameters"}
        500: {"error": "Internal server error"}
    
    Requirements: 4.6, 10.5
    """
    try:
        # Get query parameters
        status = request.args.get('status', None)
        
        # Parse limit and offset with defaults
        try:
            limit = int(request.args.get('limit', 100))
            offset = int(request.args.get('offset', 0))
        except ValueError:
            return jsonify({
                "error": "Invalid parameters",
                "message": "limit and offset must be integers"
            }), 400
        
        # Validate limit and offset
        if limit < 1 or limit > 1000:
            return jsonify({
                "error": "Invalid limit",
                "message": "limit must be between 1 and 1000"
            }), 400
        
        if offset < 0:
            return jsonify({
                "error": "Invalid offset",
                "message": "offset must be >= 0"
            }), 400
        
        # Import license service
        from ..utils.license_service import list_licenses as list_licenses_service
        
        # Get licenses
        result = list_licenses_service(status, limit, offset)
        
        # Add active_sessions count for each license
        with db_pool.get_cursor() as cursor:
            for license_data in result['licenses']:
                active_count = Session.count_active(cursor, license_data['key'])
                license_data['active_sessions'] = active_count
        
        logger.info(f"Listed {len(result['licenses'])} licenses (status={status}, limit={limit}, offset={offset})")
        
        return jsonify(result), 200
        
    except ValueError as e:
        # Invalid status parameter
        logger.warning(f"Invalid parameters for list licenses: {str(e)}")
        return jsonify({
            "error": "Invalid parameters",
            "message": str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error listing licenses: {e}", exc_info=True)
        return jsonify({
            "error": "Internal server error",
            "message": "Failed to list licenses"
        }), 500


@admin_bp.route('/sessions', methods=['GET'])
@require_admin_auth
def list_sessions():
    """
    View active sessions.
    
    This endpoint retrieves active sessions with optional filtering by license key.
    
    Headers:
        Authorization: Bearer {admin_token}
    
    Query parameters:
        license_key: optional filter
    
    Response:
        200: {"sessions": [...]}
        400: {"error": "Invalid parameters"}
        500: {"error": "Internal server error"}
    
    Requirements: 10.5
    """
    try:
        # Get query parameter
        license_key = request.args.get('license_key', None)
        
        # Validate license key format if provided
        if license_key and len(license_key) != 25:
            return jsonify({
                "error": "Invalid license key format",
                "message": "License key must be 25 characters"
            }), 400
        
        with db_pool.get_cursor() as cursor:
            if license_key:
                # Get sessions for specific license
                sessions = Session.get_by_license_key(cursor, license_key)
            else:
                # Get all sessions
                cursor.execute("""
                    SELECT * FROM sessions 
                    ORDER BY created_at DESC
                """)
                rows = cursor.fetchall()
                sessions = [Session(row) for row in rows]
            
            # Convert sessions to dictionaries
            session_list = [session.to_dict() for session in sessions]
        
        logger.info(f"Listed {len(session_list)} sessions (license_key={license_key})")
        
        return jsonify({
            "sessions": session_list
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing sessions: {e}", exc_info=True)
        return jsonify({
            "error": "Internal server error",
            "message": "Failed to list sessions"
        }), 500
