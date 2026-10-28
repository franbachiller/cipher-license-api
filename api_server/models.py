"""
Database models for License and Session.

These models provide helper methods for common database operations
and encapsulate the database schema defined in schema.sql.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime


class License:
    """
    License model representing a license key in the system.
    
    Attributes:
        id: Primary key
        key: 25-character license key (unique)
        status: License status (active, expired, revoked)
        expires_at: Expiration timestamp
        max_sessions: Maximum concurrent sessions allowed
        created_at: Creation timestamp
        note: Optional admin note
    """
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize License from database row."""
        self.id = data.get('id')
        self.key = data.get('key')
        self.status = data.get('status')
        self.expires_at = data.get('expires_at')
        self.max_sessions = data.get('max_sessions')
        self.created_at = data.get('created_at')
        self.note = data.get('note')
        self.hwid = data.get('hwid')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert License to dictionary."""
        return {
            'id': self.id,
            'key': self.key,
            'status': self.status,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'max_sessions': self.max_sessions,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'note': self.note
        }
    
    @staticmethod
    def find_by_key(cursor, license_key: str) -> Optional['License']:
        """
        Find license by key.
        
        Args:
            cursor: Database cursor
            license_key: License key to search for
        
        Returns:
            License instance or None if not found
        """
        cursor.execute(
            "SELECT * FROM licenses WHERE key = %s",
            (license_key,)
        )
        row = cursor.fetchone()
        return License(row) if row else None
    
    @staticmethod
    def create(cursor, key: str, expires_at: datetime, max_sessions: int, note: str = '') -> 'License':
        """
        Create a new license.
        
        Args:
            cursor: Database cursor
            key: License key
            expires_at: Expiration timestamp
            max_sessions: Maximum concurrent sessions
            note: Optional admin note
        
        Returns:
            Created License instance
        """
        cursor.execute(
            """
            INSERT INTO licenses (key, status, expires_at, max_sessions, note)
            VALUES (%s, 'active', %s, %s, %s)
            RETURNING *
            """,
            (key, expires_at, max_sessions, note)
        )
        row = cursor.fetchone()
        return License(row)
    
    @staticmethod
    def list_all(cursor, status: Optional[str] = None, limit: int = 100, offset: int = 0) -> List['License']:
        """
        List licenses with optional filtering.
        
        Args:
            cursor: Database cursor
            status: Optional status filter (active, expired, revoked)
            limit: Maximum number of results
            offset: Offset for pagination
        
        Returns:
            List of License instances
        """
        if status:
            cursor.execute(
                """
                SELECT * FROM licenses 
                WHERE status = %s 
                ORDER BY created_at DESC 
                LIMIT %s OFFSET %s
                """,
                (status, limit, offset)
            )
        else:
            cursor.execute(
                """
                SELECT * FROM licenses 
                ORDER BY created_at DESC 
                LIMIT %s OFFSET %s
                """,
                (limit, offset)
            )
        rows = cursor.fetchall()
        return [License(row) for row in rows]
    
    @staticmethod
    def update_status(cursor, license_key: str, new_status: str) -> bool:
        """
        Update license status.
        
        Args:
            cursor: Database cursor
            license_key: License key to update
            new_status: New status (active, expired, revoked)
        
        Returns:
            True if license was updated, False if not found
        """
        cursor.execute(
            "UPDATE licenses SET status = %s WHERE key = %s",
            (new_status, license_key)
        )
        return cursor.rowcount > 0
    
    @staticmethod
    def update_expires_at(cursor, license_key: str, new_expires_at: datetime) -> bool:
        cursor.execute(
            "UPDATE licenses SET expires_at = %s WHERE key = %s",
            (new_expires_at, license_key)
        )
        return cursor.rowcount > 0

    @staticmethod
    def reset_hwid(cursor, license_key: str) -> bool:
        """Clear the HWID binding for a license (allows rebind on next login)."""
        cursor.execute(
            "UPDATE licenses SET hwid = NULL WHERE key = %s",
            (license_key,)
        )
        return cursor.rowcount > 0

    @staticmethod
    def update_note(cursor, license_key: str, note: str) -> bool:
        """Update the admin note for a license."""
        cursor.execute(
            "UPDATE licenses SET note = %s WHERE key = %s",
            (note, license_key)
        )
        return cursor.rowcount > 0

    @staticmethod
    def delete(cursor, license_key: str) -> bool:
        """Permanently delete a license and all its sessions."""
        cursor.execute("DELETE FROM sessions WHERE license_key = %s", (license_key,))
        cursor.execute("DELETE FROM licenses WHERE key = %s", (license_key,))
        return cursor.rowcount > 0



class Session:
    """
    Session model representing an active user session.
    
    Attributes:
        id: Primary key
        license_key: Foreign key to licenses table
        jwt_token_hash: SHA-256 hash of JWT token
        ip_address: Client IP address
        last_seen: Last heartbeat timestamp
        expires_at: Session expiration timestamp
        created_at: Creation timestamp
    """
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize Session from database row."""
        self.id = data.get('id')
        self.license_key = data.get('license_key')
        self.jwt_token_hash = data.get('jwt_token_hash')
        self.ip_address = data.get('ip_address')
        self.last_seen = data.get('last_seen')
        self.expires_at = data.get('expires_at')
        self.created_at = data.get('created_at')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Session to dictionary."""
        return {
            'id': self.id,
            'license_key': self.license_key,
            'ip_address': self.ip_address,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @staticmethod
    def create(cursor, license_key: str, jwt_token_hash: str, ip_address: str, expires_at: datetime) -> 'Session':
        """
        Create a new session.
        
        Args:
            cursor: Database cursor
            license_key: License key
            jwt_token_hash: SHA-256 hash of JWT token
            ip_address: Client IP address
            expires_at: Session expiration timestamp
        
        Returns:
            Created Session instance
        """
        cursor.execute(
            """
            INSERT INTO sessions (license_key, jwt_token_hash, ip_address, expires_at)
            VALUES (%s, %s, %s, %s)
            RETURNING *
            """,
            (license_key, jwt_token_hash, ip_address, expires_at)
        )
        row = cursor.fetchone()
        return Session(row)
    
    @staticmethod
    def count_active(cursor, license_key: str) -> int:
        """
        Count active sessions for a license key.
        
        Args:
            cursor: Database cursor
            license_key: License key to count sessions for
        
        Returns:
            Number of active sessions
        """
        cursor.execute(
            """
            SELECT COUNT(*) as count 
            FROM sessions 
            WHERE license_key = %s AND expires_at > CURRENT_TIMESTAMP
            """,
            (license_key,)
        )
        row = cursor.fetchone()
        return row['count'] if row else 0
    
    @staticmethod
    def update_heartbeat(cursor, jwt_token_hash: str) -> bool:
        """
        Update last_seen timestamp for a session.
        
        Args:
            cursor: Database cursor
            jwt_token_hash: SHA-256 hash of JWT token
        
        Returns:
            True if session was updated, False if not found
        """
        cursor.execute(
            """
            UPDATE sessions 
            SET last_seen = CURRENT_TIMESTAMP 
            WHERE jwt_token_hash = %s
            """,
            (jwt_token_hash,)
        )
        return cursor.rowcount > 0
    
    @staticmethod
    def delete_expired(cursor) -> int:
        """
        Delete expired sessions.
        
        Args:
            cursor: Database cursor
        
        Returns:
            Number of sessions deleted
        """
        cursor.execute(
            """
            DELETE FROM sessions 
            WHERE expires_at < CURRENT_TIMESTAMP 
               OR last_seen < CURRENT_TIMESTAMP - INTERVAL '90 seconds'
            """
        )
        return cursor.rowcount
    
    @staticmethod
    def get_by_license_key(cursor, license_key: str) -> List['Session']:
        """
        Get all sessions for a license key.
        
        Args:
            cursor: Database cursor
            license_key: License key to get sessions for
        
        Returns:
            List of Session instances
        """
        cursor.execute(
            """
            SELECT * FROM sessions 
            WHERE license_key = %s 
            ORDER BY created_at DESC
            """,
            (license_key,)
        )
        rows = cursor.fetchall()
        return [Session(row) for row in rows]
    
    @staticmethod
    def delete_by_license_key(cursor, license_key: str) -> int:
        """
        Delete all sessions for a license key.
        
        Args:
            cursor: Database cursor
            license_key: License key to delete sessions for
        
        Returns:
            Number of sessions deleted
        """
        cursor.execute(
            "DELETE FROM sessions WHERE license_key = %s",
            (license_key,)
        )
        return cursor.rowcount
