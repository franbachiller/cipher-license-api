"""
AES encryption and decryption utilities for binary data.

This module provides AES-256-CBC encryption and decryption functions
for securing binary files stored on the VPS server.
"""

import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding


def encrypt_binary(data: bytes, key: bytes) -> bytes:
    """
    Encrypt binary data using AES-256-CBC.
    
    Generates a random 16-byte IV for each encryption operation,
    applies PKCS7 padding to the plaintext, encrypts with AES-256-CBC,
    and prepends the IV to the ciphertext for storage.
    
    Args:
        data: Binary data to encrypt
        key: 32-byte AES encryption key
    
    Returns:
        IV (16 bytes) + encrypted data
        
    Raises:
        ValueError: If key is not 32 bytes
    """
    if len(key) != 32:
        raise ValueError("AES-256 requires a 32-byte key")
    
    # Generate random 16-byte IV
    iv = os.urandom(16)
    
    # Apply PKCS7 padding to plaintext
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(data) + padder.finalize()
    
    # Encrypt with AES-256-CBC
    cipher = Cipher(
        algorithms.AES(key),
        modes.CBC(iv),
        backend=default_backend()
    )
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()
    
    # Prepend IV to ciphertext
    return iv + ciphertext


def decrypt_binary(data: bytes, key: bytes) -> bytes:
    """
    Decrypt binary data using AES-256-CBC.
    
    Extracts the IV from the first 16 bytes, decrypts the remaining
    bytes using AES-256-CBC, and removes PKCS7 padding.
    
    Args:
        data: IV (16 bytes) + encrypted data
        key: 32-byte AES encryption key
    
    Returns:
        Decrypted binary data
        
    Raises:
        ValueError: If key is not 32 bytes or data is too short
    """
    if len(key) != 32:
        raise ValueError("AES-256 requires a 32-byte key")
    
    if len(data) < 16:
        raise ValueError("Encrypted data must be at least 16 bytes (IV)")
    
    # Extract IV from first 16 bytes
    iv = data[:16]
    ciphertext = data[16:]
    
    # Decrypt with AES-256-CBC
    cipher = Cipher(
        algorithms.AES(key),
        modes.CBC(iv),
        backend=default_backend()
    )
    decryptor = cipher.decryptor()
    padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()
    
    # Remove PKCS7 padding
    unpadder = padding.PKCS7(128).unpadder()
    plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()
    
    return plaintext
