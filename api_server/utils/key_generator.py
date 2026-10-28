"""
License key generation utilities using cryptographically secure random generation.
"""

import secrets
import string
from typing import Optional, Callable

try:
    from ..database import db_pool
except ImportError:
    # Allow import without database for testing
    db_pool = None


# Character set for license keys: uppercase letters and digits
KEY_CHARSET = string.ascii_uppercase + string.digits
KEY_LENGTH = 25


def generate_license_key(key_exists_fn: Optional[Callable[[str], bool]] = None) -> str:
    """
    Generate a cryptographically secure 25-character alphanumeric license key.
    
    The key is generated using the secrets module for cryptographic randomness
    and consists of uppercase letters (A-Z) and digits (0-9).
    
    This function ensures uniqueness by checking the database before returning.
    If a duplicate is found, it generates a new key recursively.
    
    Args:
        key_exists_fn: Optional function to check if key exists. If None, uses _key_exists.
    
    Returns:
        str: A unique 25-character alphanumeric license key
        
    Raises:
        Exception: If database connection fails or query errors occur
        
    Example:
        >>> key = generate_license_key()
        >>> len(key)
        25
        >>> all(c in KEY_CHARSET for c in key)
        True
    """
    # Generate a random 25-character key
    key = ''.join(secrets.choice(KEY_CHARSET) for _ in range(KEY_LENGTH))
    
    # Check uniqueness in database
    check_fn = key_exists_fn if key_exists_fn is not None else _key_exists
    if check_fn(key):
        # Recursively generate a new key if duplicate found
        return generate_license_key(key_exists_fn)
    
    return key


def _key_exists(key: str) -> bool:
    """
    Check if a license key already exists in the database.
    
    Args:
        key: The license key to check
        
    Returns:
        bool: True if the key exists, False otherwise
        
    Raises:
        Exception: If database connection fails or query errors occur
    """
    if db_pool is None:
        raise Exception("Database pool not initialized")
    
    with db_pool.get_cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM licenses WHERE key = %s LIMIT 1",
            (key,)
        )
        result = cursor.fetchone()
        return result is not None


def validate_key_format(key: str) -> bool:
    """
    Validate that a license key matches the expected format.
    
    A valid license key must be:
    - Exactly 25 characters long
    - Contain only uppercase letters (A-Z) and digits (0-9)
    
    Args:
        key: The license key to validate
        
    Returns:
        bool: True if the key format is valid, False otherwise
        
    Example:
        >>> validate_key_format("ABCD1234EFGH5678IJKL90MNO")
        True
        >>> validate_key_format("abcd1234efgh5678ijkl90mno")  # lowercase
        False
        >>> validate_key_format("ABCD1234")  # too short
        False
        >>> validate_key_format("ABCD1234EFGH5678IJKL90MN@")  # invalid char
        False
    """
    if len(key) != KEY_LENGTH:
        return False
    
    return all(c in KEY_CHARSET for c in key)
