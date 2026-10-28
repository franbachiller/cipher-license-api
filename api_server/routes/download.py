"""
Binary download route handlers.

This module provides endpoints for downloading encrypted binaries (loader, driver, cheat).
All endpoints require valid JWT authentication and stream encrypted binary data to clients.

Requirements: 2.1, 2.2, 2.5
"""

import os
from flask import request, jsonify, send_file, current_app
from . import download_bp
from ..middleware.jwt_validator import require_jwt_auth


@download_bp.route('/loader', methods=['GET'])
@require_jwt_auth
def download_loader(jwt_payload):
    """
    Download encrypted GDRVLoader.exe binary.
    
    This endpoint streams the encrypted loader binary to authenticated clients.
    The JWT middleware handles authentication (401) and IP validation (403).
    
    Headers:
        Authorization: Bearer {jwt_token}
    
    Response:
        200: Binary stream (application/octet-stream) - IV (16 bytes) + encrypted data
        401: Invalid or expired JWT (handled by middleware)
        403: IP address mismatch (handled by middleware)
        500: Server error (file not found or read error)
    
    Requirements: 2.1, 2.2, 2.5
    """
    try:
        # Construct path to encrypted binary
        binary_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'binaries',
            'loader.enc'
        )
        
        # Check if file exists
        if not os.path.exists(binary_path):
            current_app.logger.error(f"Encrypted loader binary not found at {binary_path}")
            return jsonify({
                "error": "Binary not found",
                "message": "Encrypted loader binary is not available on the server"
            }), 500
        
        # Stream binary file to client
        return send_file(
            binary_path,
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name='loader.enc'
        )
        
    except Exception as e:
        current_app.logger.error(f"Error downloading loader binary: {str(e)}")
        return jsonify({
            "error": "Download failed",
            "message": "An error occurred while downloading the binary"
        }), 500


@download_bp.route('/driver', methods=['GET'])
@require_jwt_auth
def download_driver(jwt_payload):
    """
    Download encrypted driver.sys binary.
    
    This endpoint streams the encrypted driver binary to authenticated clients.
    The JWT middleware handles authentication (401) and IP validation (403).
    
    Headers:
        Authorization: Bearer {jwt_token}
    
    Response:
        200: Binary stream (application/octet-stream) - IV (16 bytes) + encrypted data
        401: Invalid or expired JWT (handled by middleware)
        403: IP address mismatch (handled by middleware)
        500: Server error (file not found or read error)
    
    Requirements: 2.1, 2.2, 2.5
    """
    try:
        # Construct path to encrypted binary
        binary_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'binaries',
            'driver.enc'
        )
        
        # Check if file exists
        if not os.path.exists(binary_path):
            current_app.logger.error(f"Encrypted driver binary not found at {binary_path}")
            return jsonify({
                "error": "Binary not found",
                "message": "Encrypted driver binary is not available on the server"
            }), 500
        
        # Stream binary file to client
        return send_file(
            binary_path,
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name='driver.enc'
        )
        
    except Exception as e:
        current_app.logger.error(f"Error downloading driver binary: {str(e)}")
        return jsonify({
            "error": "Download failed",
            "message": "An error occurred while downloading the binary"
        }), 500


@download_bp.route('/cheat', methods=['GET'])
@require_jwt_auth
def download_cheat(jwt_payload):
    """
    Download encrypted Cipher.exe binary.
    
    This endpoint streams the encrypted cheat binary to authenticated clients.
    The JWT middleware handles authentication (401) and IP validation (403).
    
    Headers:
        Authorization: Bearer {jwt_token}
    
    Response:
        200: Binary stream (application/octet-stream) - IV (16 bytes) + encrypted data
        401: Invalid or expired JWT (handled by middleware)
        403: IP address mismatch (handled by middleware)
        500: Server error (file not found or read error)
    
    Requirements: 2.1, 2.2, 2.5
    """
    try:
        # Construct path to encrypted binary
        binary_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'binaries',
            'cheat.enc'
        )
        
        # Check if file exists
        if not os.path.exists(binary_path):
            current_app.logger.error(f"Encrypted cheat binary not found at {binary_path}")
            return jsonify({
                "error": "Binary not found",
                "message": "Encrypted cheat binary is not available on the server"
            }), 500
        
        # Stream binary file to client
        return send_file(
            binary_path,
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name='cheat.enc'
        )
        
    except Exception as e:
        current_app.logger.error(f"Error downloading cheat binary: {str(e)}")
        return jsonify({
            "error": "Download failed",
            "message": "An error occurred while downloading the binary"
        }), 500
