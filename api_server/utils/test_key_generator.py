"""
Unit tests for license key generation utilities.
"""

import pytest
import string
import sys
import os
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from api_server.utils.key_generator import (
    generate_license_key,
    validate_key_format,
    KEY_CHARSET,
    KEY_LENGTH,
    _key_exists
)


class TestKeyGeneration:
    """Tests for license key generation."""
    
    def test_generate_key_length(self):
        """Test that generated keys are exactly 25 characters long."""
        with patch('api_server.utils.key_generator._key_exists', return_value=False):
            key = generate_license_key()
            assert len(key) == KEY_LENGTH
    
    def test_generate_key_charset(self):
        """Test that generated keys only contain valid characters (A-Z, 0-9)."""
        with patch('api_server.utils.key_generator._key_exists', return_value=False):
            key = generate_license_key()
            assert all(c in KEY_CHARSET for c in key)
    
    def test_generate_key_uppercase_only(self):
        """Test that generated keys contain only uppercase letters and digits."""
        with patch('api_server.utils.key_generator._key_exists', return_value=False):
            key = generate_license_key()
            # Should not contain lowercase letters
            assert not any(c in string.ascii_lowercase for c in key)
    
    def test_generate_key_uniqueness_check(self):
        """Test that key generation checks database for uniqueness."""
        mock_exists = MagicMock(side_effect=[True, True, False])
        
        with patch('api_server.utils.key_generator._key_exists', mock_exists):
            key = generate_license_key()
            
            # Should have called _key_exists 3 times (2 duplicates, then unique)
            assert mock_exists.call_count == 3
            assert len(key) == KEY_LENGTH
    
    def test_generate_multiple_keys_are_different(self):
        """Test that multiple generated keys are different (high probability)."""
        with patch('api_server.utils.key_generator._key_exists', return_value=False):
            keys = [generate_license_key() for _ in range(10)]
            
            # All keys should be unique (extremely high probability with 25 chars)
            assert len(set(keys)) == 10


class TestKeyValidation:
    """Tests for license key format validation."""
    
    def test_validate_valid_key(self):
        """Test that valid keys pass validation."""
        valid_key = "ABCD1234EFGH5678IJKL90MNO"
        assert validate_key_format(valid_key) is True
    
    def test_validate_all_letters(self):
        """Test that keys with all letters are valid."""
        valid_key = "ABCDEFGHIJKLMNOPQRSTUVWXY"
        assert validate_key_format(valid_key) is True
    
    def test_validate_all_digits(self):
        """Test that keys with all digits are valid."""
        valid_key = "1234567890123456789012345"
        assert validate_key_format(valid_key) is True
    
    def test_validate_too_short(self):
        """Test that keys shorter than 25 characters are invalid."""
        short_key = "ABCD1234"
        assert validate_key_format(short_key) is False
    
    def test_validate_too_long(self):
        """Test that keys longer than 25 characters are invalid."""
        long_key = "ABCD1234EFGH5678IJKL90MNOEXTRA"
        assert validate_key_format(long_key) is False
    
    def test_validate_lowercase_letters(self):
        """Test that keys with lowercase letters are invalid."""
        lowercase_key = "abcd1234efgh5678ijkl90mno"
        assert validate_key_format(lowercase_key) is False
    
    def test_validate_mixed_case(self):
        """Test that keys with mixed case are invalid."""
        mixed_key = "ABCD1234efgh5678IJKL90MNO"
        assert validate_key_format(mixed_key) is False
    
    def test_validate_special_characters(self):
        """Test that keys with special characters are invalid."""
        special_key = "ABCD1234EFGH5678IJKL90MN@"
        assert validate_key_format(special_key) is False
    
    def test_validate_spaces(self):
        """Test that keys with spaces are invalid."""
        space_key = "ABCD 1234 EFGH 5678 IJKL"
        assert validate_key_format(space_key) is False
    
    def test_validate_empty_string(self):
        """Test that empty string is invalid."""
        assert validate_key_format("") is False
    
    def test_validate_hyphens(self):
        """Test that keys with hyphens are invalid."""
        hyphen_key = "ABCD-1234-EFGH-5678-IJKL"
        assert validate_key_format(hyphen_key) is False


class TestKeyExistence:
    """Tests for database key existence checking."""
    
    def test_key_exists_returns_true_when_found(self):
        """Test that _key_exists returns True when key is in database."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {'id': 1}
        
        mock_pool = MagicMock()
        mock_pool.get_cursor.return_value.__enter__.return_value = mock_cursor
        
        with patch('api_server.utils.key_generator.db_pool', mock_pool):
            result = _key_exists("TESTKEY12345678901234567")
            assert result is True
    
    def test_key_exists_returns_false_when_not_found(self):
        """Test that _key_exists returns False when key is not in database."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        
        mock_pool = MagicMock()
        mock_pool.get_cursor.return_value.__enter__.return_value = mock_cursor
        
        with patch('api_server.utils.key_generator.db_pool', mock_pool):
            result = _key_exists("TESTKEY12345678901234567")
            assert result is False
    
    def test_key_exists_executes_correct_query(self):
        """Test that _key_exists executes the correct SQL query."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        
        mock_pool = MagicMock()
        mock_pool.get_cursor.return_value.__enter__.return_value = mock_cursor
        
        test_key = "TESTKEY12345678901234567"
        
        with patch('api_server.utils.key_generator.db_pool', mock_pool):
            _key_exists(test_key)
            
            # Verify the SQL query was executed with correct parameters
            mock_cursor.execute.assert_called_once()
            call_args = mock_cursor.execute.call_args
            assert "SELECT 1 FROM licenses WHERE key = %s" in call_args[0][0]
            assert call_args[0][1] == (test_key,)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
