"""
Unit tests for AES-256-CBC encryption utilities.
"""

import os
import sys
import pytest

# Add parent directory to path to import encryption module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from encryption import encrypt_binary, decrypt_binary


class TestEncryptionUtility:
    """Test suite for encryption and decryption functions."""
    
    @pytest.fixture
    def test_key(self):
        """Generate a test 32-byte AES key."""
        return os.urandom(32)
    
    @pytest.fixture
    def test_data(self):
        """Generate test binary data."""
        return b"This is test binary data for encryption testing."
    
    def test_encrypt_binary_returns_iv_plus_ciphertext(self, test_key, test_data):
        """Test that encrypted data includes IV prefix."""
        encrypted = encrypt_binary(test_data, test_key)
        
        # Should be at least 16 bytes (IV) + length of padded data
        assert len(encrypted) > 16
        # IV is first 16 bytes
        assert len(encrypted[:16]) == 16
    
    def test_encrypt_binary_with_invalid_key_length(self, test_data):
        """Test that encryption fails with invalid key length."""
        invalid_key = os.urandom(16)  # Only 16 bytes, need 32
        
        with pytest.raises(ValueError, match="32-byte key"):
            encrypt_binary(test_data, invalid_key)
    
    def test_decrypt_binary_returns_original_data(self, test_key, test_data):
        """Test encryption-decryption round trip preserves data."""
        encrypted = encrypt_binary(test_data, test_key)
        decrypted = decrypt_binary(encrypted, test_key)
        
        assert decrypted == test_data
    
    def test_decrypt_binary_with_invalid_key_length(self):
        """Test that decryption fails with invalid key length."""
        invalid_key = os.urandom(16)
        encrypted_data = os.urandom(32)  # Fake encrypted data
        
        with pytest.raises(ValueError, match="32-byte key"):
            decrypt_binary(encrypted_data, invalid_key)
    
    def test_decrypt_binary_with_too_short_data(self, test_key):
        """Test that decryption fails with data shorter than IV."""
        short_data = os.urandom(10)  # Less than 16 bytes
        
        with pytest.raises(ValueError, match="at least 16 bytes"):
            decrypt_binary(short_data, test_key)
    
    def test_encrypt_produces_different_ivs(self, test_key, test_data):
        """Test that multiple encryptions produce different IVs."""
        encrypted1 = encrypt_binary(test_data, test_key)
        encrypted2 = encrypt_binary(test_data, test_key)
        
        # Extract IVs (first 16 bytes)
        iv1 = encrypted1[:16]
        iv2 = encrypted2[:16]
        
        # IVs should be different (random)
        assert iv1 != iv2
    
    def test_encrypt_decrypt_with_various_sizes(self, test_key):
        """Test encryption/decryption with various data sizes."""
        test_sizes = [1, 15, 16, 17, 100, 1000, 10000]
        
        for size in test_sizes:
            data = os.urandom(size)
            encrypted = encrypt_binary(data, test_key)
            decrypted = decrypt_binary(encrypted, test_key)
            
            assert decrypted == data, f"Failed for size {size}"
    
    def test_encrypt_decrypt_with_empty_data(self, test_key):
        """Test encryption/decryption with empty data."""
        empty_data = b""
        encrypted = encrypt_binary(empty_data, test_key)
        decrypted = decrypt_binary(encrypted, test_key)
        
        assert decrypted == empty_data
    
    def test_decrypt_with_wrong_key_fails(self, test_data):
        """Test that decryption with wrong key produces different data."""
        key1 = os.urandom(32)
        key2 = os.urandom(32)
        
        encrypted = encrypt_binary(test_data, key1)
        
        # Decrypting with wrong key should either fail or produce garbage
        # (it won't match original data)
        try:
            decrypted = decrypt_binary(encrypted, key2)
            assert decrypted != test_data
        except Exception:
            # Padding error is also acceptable
            pass
    
    def test_iv_is_prepended_correctly(self, test_key, test_data):
        """Test that IV is correctly prepended to ciphertext."""
        encrypted = encrypt_binary(test_data, test_key)
        
        # Extract IV
        iv = encrypted[:16]
        ciphertext = encrypted[16:]
        
        # IV should be 16 bytes
        assert len(iv) == 16
        # Ciphertext should exist
        assert len(ciphertext) > 0
        # Ciphertext length should be multiple of 16 (AES block size)
        assert len(ciphertext) % 16 == 0
