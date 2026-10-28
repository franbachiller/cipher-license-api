"""
License service layer providing high-level CRUD operations.

This module provides a service layer on top of the License model,
handling license creation, revocation, extension, and listing operations.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime

from ..models import License, Session
from ..database import db_pool
from .key_generator import generate_license_key


def create_license(
    expires_at: datetime,
    max_sessions: int = 1,
    note: str = ''
) -> Dict[str, Any]:
    """
    Create a new license with a generated key.
    
    This function generates a unique license key and creates a new license
    record in the database with the specified parameters.
    
    Args:
        expires_at: Expiration timestamp for the license
        max_sessions: Maximum concurrent sessions allowed (default: 1)
        note: Optional admin note (e.g., customer ID, order number)
    
    Returns:
        Dictionary containing the created license details:
        {
            'license_key': str,
            'status': str,
            'expires_at': str (ISO format),
            'max_sessions': int,
            'created_at': str (ISO format),
            'note': str
        }
    
    Raises:
        ValueError: If max_sessions is less than 1
        Exception: If database operation fails
    
    Example:
        >>> from datetime import datetime, timedelta
        >>> expires = datetime.utcnow() + timedelta(days=30)
        >>> license = create_license(expires, max_sessions=2, note="Customer #123")
        >>> print(license['license_key'])
        'ABCD1234EFGH5678IJKL90MNO'
    """
    if max_sessions < 1:
        raise ValueError("max_sessions must be at least 1")
    
    # Generate unique license key
    key = generate_license_key()
    
    # Create license in database
    with db_pool.get_cursor(commit=True) as cursor:
        license = License.create(cursor, key, expires_at, max_sessions, note)
        
        return {
            'license_key': license.key,
            'status': license.status,
            'expires_at': license.expires_at.isoformat() if license.expires_at else None,
            'max_sessions': license.max_sessions,
            'created_at': license.created_at.isoformat() if license.created_at else None,
            'note': license.note
        }


def revoke_license(license_key: str) -> Dict[str, Any]:
    """
    Revoke a license and terminate all active sessions.
    
    This function updates the license status to "revoked" and immediately
    deletes all active sessions associated with the license key.
    
    Args:
        license_key: The license key to revoke
    
    Returns:
        Dictionary containing:
        {
            'message': str,
            'sessions_terminated': int
        }
    
    Raises:
        ValueError: If license key is not found
        Exception: If database operation fails
    
    Example:
        >>> result = revoke_license("ABCD1234EFGH5678IJKL90MNO")
        >>> print(result['sessions_terminated'])
        2
    """
    with db_pool.get_cursor(commit=True) as cursor:
        # Check if license exists
        license = License.find_by_key(cursor, license_key)
        if not license:
            raise ValueError(f"License key not found: {license_key}")
        
        # Update license status to revoked
        License.update_status(cursor, license_key, 'revoked')
        
        # Terminate all active sessions for this license
        sessions_terminated = Session.delete_by_license_key(cursor, license_key)
        
        return {
            'message': 'License revoked',
            'sessions_terminated': sessions_terminated
        }


def extend_license(license_key: str, new_expires_at: datetime) -> Dict[str, Any]:
    """
    Extend a license by updating its expiration date.
    
    This function updates the expires_at field for the specified license.
    It can be used to extend expired licenses or modify active license durations.
    
    Args:
        license_key: The license key to extend
        new_expires_at: New expiration timestamp
    
    Returns:
        Dictionary containing:
        {
            'message': str,
            'expires_at': str (ISO format)
        }
    
    Raises:
        ValueError: If license key is not found
        Exception: If database operation fails
    
    Example:
        >>> from datetime import datetime, timedelta
        >>> new_expiry = datetime.utcnow() + timedelta(days=60)
        >>> result = extend_license("ABCD1234EFGH5678IJKL90MNO", new_expiry)
        >>> print(result['message'])
        'License extended'
    """
    with db_pool.get_cursor(commit=True) as cursor:
        # Check if license exists
        license = License.find_by_key(cursor, license_key)
        if not license:
            raise ValueError(f"License key not found: {license_key}")
        
        # Update expiration date
        License.update_expires_at(cursor, license_key, new_expires_at)
        
        return {
            'message': 'License extended',
            'expires_at': new_expires_at.isoformat()
        }


def list_licenses(
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> Dict[str, Any]:
    """
    List licenses with optional status filtering.
    
    This function retrieves licenses from the database with optional filtering
    by status and pagination support.
    
    Args:
        status: Optional status filter ('active', 'expired', 'revoked')
        limit: Maximum number of results to return (default: 100)
        offset: Offset for pagination (default: 0)
    
    Returns:
        Dictionary containing:
        {
            'licenses': List[Dict],
            'total': int,
            'limit': int,
            'offset': int
        }
        
        Each license in the list contains:
        {
            'key': str,
            'status': str,
            'expires_at': str (ISO format),
            'max_sessions': int,
            'created_at': str (ISO format),
            'note': str
        }
    
    Raises:
        ValueError: If status is not one of ('active', 'expired', 'revoked', None)
        Exception: If database operation fails
    
    Example:
        >>> result = list_licenses(status='active', limit=50)
        >>> print(f"Found {len(result['licenses'])} active licenses")
        Found 25 active licenses
    """
    # Validate status parameter
    valid_statuses = {'active', 'expired', 'revoked', None}
    if status not in valid_statuses:
        raise ValueError(f"Invalid status: {status}. Must be one of: active, expired, revoked")
    
    with db_pool.get_cursor() as cursor:
        # Get licenses with optional filtering
        licenses = License.list_all(cursor, status, limit, offset)
        
        # Get total count for pagination
        if status:
            cursor.execute(
                "SELECT COUNT(*) as count FROM licenses WHERE status = %s",
                (status,)
            )
        else:
            cursor.execute("SELECT COUNT(*) as count FROM licenses")
        
        count_row = cursor.fetchone()
        total = count_row['count'] if count_row else 0
        
        # Convert licenses to dictionaries
        license_list = []
        for license in licenses:
            license_dict = license.to_dict()
            # Remove internal id field from response
            license_dict.pop('id', None)
            license_list.append(license_dict)
        
        return {
            'licenses': license_list,
            'total': total,
            'limit': limit,
            'offset': offset
        }
