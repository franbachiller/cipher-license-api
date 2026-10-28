"""
Authentication attempt logging utility.

Logs all authentication attempts with timestamp, IP, license key, and result.
Requirements: 5.4, 9.4
"""

from datetime import datetime
from typing import Optional
import logging

from ..database import db_pool


logger = logging.getLogger('cipher_api')


class AuthLogger:
    """Handles logging of authentication attempts to database and log files."""
    
    @staticmethod
    def log_auth_attempt(
        license_key: str,
        ip_address: str,
        success: bool,
        error_message: Optional[str] = None
    ) -> None:
        """
        Log an authentication attempt to database and log file.
        
        Args:
            license_key: License key used in authentication attempt
            ip_address: Client IP address
            success: Whether authentication was successful
            error_message: Error message if authentication failed
        
        Requirements: 5.4, 9.4
        """
        try:
            # Log to database
            with db_pool.get_cursor(commit=True) as cursor:
                cursor.execute(
                    """
                    INSERT INTO auth_logs (license_key, ip_address, success, error_message)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (license_key, ip_address, success, error_message)
                )
            
            # Log to file
            if success:
                logger.info(
                    f"AUTH_SUCCESS: license_key={license_key[:8]}..., "
                    f"ip={ip_address}"
                )
            else:
                logger.warning(
                    f"AUTH_FAILED: license_key={license_key[:8]}..., "
                    f"ip={ip_address}, error={error_message}"
                )
                
        except Exception as e:
            # Don't fail authentication if logging fails
            logger.error(f"Failed to log authentication attempt: {e}")
    
    @staticmethod
    def get_recent_attempts(limit: int = 100) -> list:
        """
        Get recent authentication attempts from database.
        
        Args:
            limit: Maximum number of attempts to return
        
        Returns:
            List of authentication attempt records
        """
        try:
            with db_pool.get_cursor() as cursor:
                cursor.execute(
                    """
                    SELECT license_key, ip_address, success, error_message, timestamp
                    FROM auth_logs
                    ORDER BY timestamp DESC
                    LIMIT %s
                    """,
                    (limit,)
                )
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Failed to retrieve auth logs: {e}")
            return []
    
    @staticmethod
    def get_failed_attempts_by_ip(ip_address: str, minutes: int = 60) -> int:
        """
        Count failed authentication attempts from an IP in the last N minutes.
        
        Args:
            ip_address: IP address to check
            minutes: Time window in minutes
        
        Returns:
            Number of failed attempts
        """
        try:
            with db_pool.get_cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(*) as count
                    FROM auth_logs
                    WHERE ip_address = %s
                      AND success = FALSE
                      AND timestamp > CURRENT_TIMESTAMP - INTERVAL '%s minutes'
                    """,
                    (ip_address, minutes)
                )
                row = cursor.fetchone()
                return row['count'] if row else 0
        except Exception as e:
            logger.error(f"Failed to count failed attempts: {e}")
            return 0
