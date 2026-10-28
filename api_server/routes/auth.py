"""
Authentication route handlers.
"""

from flask import request, jsonify
from datetime import datetime, timedelta
import hashlib

from . import auth_bp
from ..database import db_pool
from ..models import License, Session
from ..utils.key_generator import validate_key_format
from ..utils.jwt_utils import generate_jwt_token
from ..utils.auth_logger import AuthLogger
from ..config import Config


@auth_bp.route('/auth', methods=['POST'])
def authenticate():
    """
    Authenticate user with license key + HWID and return JWT token.
    First login binds the HWID to the license. Subsequent logins validate it.
    """
    data = request.get_json()
    
    if not data or 'license_key' not in data:
        return jsonify({"error": "Invalid request format"}), 400
    
    license_key = data['license_key']
    client_hwid = data.get('hwid', '')
    
    if not validate_key_format(license_key):
        return jsonify({"error": "Invalid license key format"}), 400
    
    ip_address = request.remote_addr
    
    # HWID is optional for backward compat but required for new clients
    if not client_hwid or len(client_hwid) < 16:
        client_hwid = None
    
    try:
        with db_pool.get_cursor(commit=True) as cursor:
            license = License.find_by_key(cursor, license_key)
            
            if not license:
                AuthLogger.log_auth_attempt(license_key, ip_address, False, "Invalid license key")
                return jsonify({"error": "Invalid license key"}), 401
            
            if license.status == 'revoked':
                AuthLogger.log_auth_attempt(license_key, ip_address, False, "License revoked")
                return jsonify({"error": "License revoked"}), 403
            
            if license.status == 'expired':
                AuthLogger.log_auth_attempt(license_key, ip_address, False, "License expired")
                return jsonify({"error": "License expired"}), 403
            
            if license.status != 'active':
                AuthLogger.log_auth_attempt(license_key, ip_address, False, "License not active")
                return jsonify({"error": "License not active"}), 403
            
            current_time = datetime.utcnow()
            if license.expires_at and license.expires_at < current_time:
                AuthLogger.log_auth_attempt(license_key, ip_address, False, "License expired")
                return jsonify({"error": "License expired"}), 403
            
            # HWID binding: bind on first use, validate on subsequent
            if client_hwid:
                stored_hwid = getattr(license, 'hwid', None)
                if stored_hwid and stored_hwid != '':
                    if stored_hwid != client_hwid:
                        AuthLogger.log_auth_attempt(license_key, ip_address, False, "HWID mismatch")
                        return jsonify({"error": "License bound to another machine"}), 403
                else:
                    # First login — bind HWID
                    cursor.execute(
                        "UPDATE licenses SET hwid = %s WHERE key = %s",
                        (client_hwid, license_key)
                    )
            
            # Clean expired sessions AND old sessions for this key (re-login always works)
            Session.delete_expired(cursor)
            Session.delete_by_license_key(cursor, license_key)
            
            active_session_count = 0  # We just cleaned them
            
            if active_session_count >= license.max_sessions:
                AuthLogger.log_auth_attempt(license_key, ip_address, False, "Session limit reached")
                return jsonify({"error": "Session limit reached"}), 429
            
            jwt_token = generate_jwt_token(license_key, ip_address)
            expires_at = current_time + timedelta(minutes=Config.JWT_EXPIRATION_MINUTES)
            jwt_token_hash = hashlib.sha256(jwt_token.encode()).hexdigest()
            
            Session.create(cursor, license_key, jwt_token_hash, ip_address, expires_at)
            
            AuthLogger.log_auth_attempt(license_key, ip_address, True, None)
            
            return jsonify({
                "jwt_token": jwt_token,
                "expires_at": expires_at.isoformat() + 'Z',
                "message": "Authentication successful"
            }), 200
            
    except Exception as e:
        AuthLogger.log_auth_attempt(license_key, ip_address, False, f"Internal error: {str(e)}")
        print(f"Authentication error: {e}")
        return jsonify({"error": "Internal server error"}), 500
