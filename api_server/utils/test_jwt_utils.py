"""
Unit tests for JWT token generation and validation.
"""

import pytest
import jwt
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path to import modules without triggering app initialization
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.jwt_utils import generate_jwt_token, decode_jwt_token
from config import Config


class TestJWTTokenGeneration:
    """Test JWT token generation functionality."""
    
    def test_generate_jwt_token_returns_string(self):
        """Test that generate_jwt_token returns a string token."""
        token = generate_jwt_token('ABCD1234EFGH5678IJKL90MNO', '192.168.1.100')
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_generate_jwt_token_contains_required_claims(self):
        """Test that generated token contains license_key, ip_address, iat, and exp claims."""
        license_key = 'ABCD1234EFGH5678IJKL90MNO'
        ip_address = '192.168.1.100'
        
        token = generate_jwt_token(license_key, ip_address)
        
        # Decode without verification to inspect claims
        payload = jwt.decode(token, options={"verify_signature": False})
        
        assert 'license_key' in payload
        assert 'ip_address' in payload
        assert 'iat' in payload
        assert 'exp' in payload
        
        assert payload['license_key'] == license_key
        assert payload['ip_address'] == ip_address
    
    def test_generate_jwt_token_has_correct_expiration(self):
        """Test that token expires in JWT_EXPIRATION_MINUTES (5 minutes by default)."""
        before_time = datetime.utcnow().replace(microsecond=0)
        token = generate_jwt_token('ABCD1234EFGH5678IJKL90MNO', '192.168.1.100')
        after_time = datetime.utcnow()
        
        payload = jwt.decode(token, options={"verify_signature": False})
        
        iat = datetime.fromtimestamp(payload['iat'])
        exp = datetime.fromtimestamp(payload['exp'])
        
        # Check that iat is between before and after
        assert before_time <= iat <= after_time
        
        # Check that exp is approximately 5 minutes after iat
        expected_expiration = iat + timedelta(minutes=Config.JWT_EXPIRATION_MINUTES)
        time_diff = abs((exp - expected_expiration).total_seconds())
        assert time_diff < 2  # Allow 2 second tolerance
    
    def test_generate_jwt_token_uses_hs256_algorithm(self):
        """Test that token uses HS256 algorithm."""
        token = generate_jwt_token('ABCD1234EFGH5678IJKL90MNO', '192.168.1.100')
        
        # Decode header without verification
        header = jwt.get_unverified_header(token)
        
        assert header['alg'] == 'HS256'
        assert header['typ'] == 'JWT'
    
    def test_generate_jwt_token_is_signed_with_secret_key(self):
        """Test that token can be verified with the configured secret key."""
        token = generate_jwt_token('ABCD1234EFGH5678IJKL90MNO', '192.168.1.100')
        
        # This should not raise an exception
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
        
        assert payload is not None


class TestJWTTokenDecoding:
    """Test JWT token decoding and validation functionality."""
    
    def test_decode_jwt_token_returns_payload(self):
        """Test that decode_jwt_token returns the token payload."""
        license_key = 'ABCD1234EFGH5678IJKL90MNO'
        ip_address = '192.168.1.100'
        
        token = generate_jwt_token(license_key, ip_address)
        payload = decode_jwt_token(token)
        
        assert isinstance(payload, dict)
        assert payload['license_key'] == license_key
        assert payload['ip_address'] == ip_address
    
    def test_decode_jwt_token_validates_signature(self):
        """Test that decode_jwt_token rejects tokens with invalid signatures."""
        # Create a token with a different secret
        payload = {
            'license_key': 'ABCD1234EFGH5678IJKL90MNO',
            'ip_address': '192.168.1.100',
            'iat': int(datetime.utcnow().timestamp()),
            'exp': int((datetime.utcnow() + timedelta(minutes=5)).timestamp())
        }
        
        invalid_token = jwt.encode(payload, 'wrong-secret-key', algorithm='HS256')
        
        with pytest.raises(jwt.InvalidTokenError):
            decode_jwt_token(invalid_token)
    
    def test_decode_jwt_token_rejects_expired_tokens(self):
        """Test that decode_jwt_token rejects expired tokens."""
        # Create an expired token
        payload = {
            'license_key': 'ABCD1234EFGH5678IJKL90MNO',
            'ip_address': '192.168.1.100',
            'iat': int((datetime.utcnow() - timedelta(minutes=10)).timestamp()),
            'exp': int((datetime.utcnow() - timedelta(minutes=5)).timestamp())
        }
        
        expired_token = jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm='HS256')
        
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_jwt_token(expired_token)
    
    def test_decode_jwt_token_rejects_malformed_tokens(self):
        """Test that decode_jwt_token rejects malformed tokens."""
        malformed_tokens = [
            'not.a.token',
            'invalid',
            '',
            'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature'
        ]
        
        for token in malformed_tokens:
            with pytest.raises(jwt.InvalidTokenError):
                decode_jwt_token(token)
    
    def test_decode_jwt_token_preserves_all_claims(self):
        """Test that all claims are preserved during encode/decode cycle."""
        license_key = 'TESTKEY1234567890123456789'
        ip_address = '10.0.0.1'
        
        token = generate_jwt_token(license_key, ip_address)
        payload = decode_jwt_token(token)
        
        assert payload['license_key'] == license_key
        assert payload['ip_address'] == ip_address
        assert 'iat' in payload
        assert 'exp' in payload
        assert isinstance(payload['iat'], int)
        assert isinstance(payload['exp'], int)


class TestJWTTokenEdgeCases:
    """Test edge cases and special scenarios."""
    
    def test_generate_jwt_token_with_ipv6_address(self):
        """Test token generation with IPv6 address."""
        token = generate_jwt_token('ABCD1234EFGH5678IJKL90MNO', '2001:0db8:85a3:0000:0000:8a2e:0370:7334')
        payload = decode_jwt_token(token)
        
        assert payload['ip_address'] == '2001:0db8:85a3:0000:0000:8a2e:0370:7334'
    
    def test_generate_jwt_token_with_special_characters_in_license_key(self):
        """Test token generation with various license key formats."""
        # Although the spec says alphanumeric only, test that the JWT encoding handles it
        license_keys = [
            'ABCDEFGHIJKLMNOPQRSTUVWXY',  # All letters
            '12345678901234567890123456',  # All numbers (26 chars for test)
            'ABC123DEF456GHI789JKL012M'    # Mixed
        ]
        
        for key in license_keys:
            token = generate_jwt_token(key, '192.168.1.1')
            payload = decode_jwt_token(token)
            assert payload['license_key'] == key
    
    def test_multiple_tokens_are_unique(self):
        """Test that generating multiple tokens produces different tokens due to different iat."""
        import time
        
        token1 = generate_jwt_token('ABCD1234EFGH5678IJKL90MNO', '192.168.1.100')
        time.sleep(1)  # Wait 1 second to ensure different iat
        token2 = generate_jwt_token('ABCD1234EFGH5678IJKL90MNO', '192.168.1.100')
        
        assert token1 != token2
    
    def test_tokens_for_different_ips_are_different(self):
        """Test that tokens for different IP addresses are different."""
        token1 = generate_jwt_token('ABCD1234EFGH5678IJKL90MNO', '192.168.1.100')
        token2 = generate_jwt_token('ABCD1234EFGH5678IJKL90MNO', '192.168.1.101')
        
        assert token1 != token2
        
        payload1 = decode_jwt_token(token1)
        payload2 = decode_jwt_token(token2)
        
        assert payload1['ip_address'] != payload2['ip_address']
