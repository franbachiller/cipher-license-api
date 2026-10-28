"""
Unit tests for JWT validation middleware.

Tests the require_jwt_auth decorator for:
- Token extraction from Authorization header
- Signature validation
- Expiration checking
- IP address verification
- Error handling for various failure scenarios

Requirements: 13.3, 13.4, 13.6
"""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import jwt
import os
import sys

# Set environment variables before importing config
os.environ.setdefault('JWT_SECRET_KEY', 'test_secret_key_for_unit_tests_only')
os.environ.setdefault('SECRET_KEY', 'test_flask_secret_key')
os.environ.setdefault('DATABASE_URL', 'postgresql://test:test@localhost/test')

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from api_server.middleware.jwt_validator import require_jwt_auth
from api_server.config import Config


class TestJWTValidationMiddleware(unittest.TestCase):
    """Test suite for JWT validation middleware."""
    
    def setUp(self):
        """Set up test fixtures."""
        from flask import Flask
        self.app_context = Flask(__name__).app_context()
        self.app_context.push()
        self.addCleanup(self.app_context.pop)
        self.test_license_key = "ABCD1234EFGH5678IJKL90MNO"
        self.test_ip = "192.168.1.100"
        self.test_secret = Config.JWT_SECRET_KEY
        
        # Create a mock Flask route function
        @require_jwt_auth
        def mock_route(jwt_payload):
            return {"success": True, "payload": jwt_payload}, 200
        
        self.mock_route = mock_route
    
    def _generate_valid_token(self, ip_address=None, expires_in_minutes=5):
        """Helper to generate a valid JWT token."""
        if ip_address is None:
            ip_address = self.test_ip
        
        current_time = datetime.utcnow()
        expiration_time = current_time + timedelta(minutes=expires_in_minutes)
        
        payload = {
            'license_key': self.test_license_key,
            'ip_address': ip_address,
            'iat': int(current_time.timestamp()),
            'exp': int(expiration_time.timestamp())
        }
        
        token = jwt.encode(payload, self.test_secret, algorithm='HS256')
        return token
    
    def _create_mock_request(self, auth_header=None, remote_addr=None):
        """Helper to create a mock Flask request object."""
        mock_request = Mock()
        mock_request.headers = Mock()
        mock_request.headers.get = Mock(return_value=auth_header)
        mock_request.remote_addr = remote_addr or self.test_ip
        return mock_request
    
    def test_valid_token_passes_validation(self):
        """Test that a valid JWT token passes all validation checks."""
        token = self._generate_valid_token()
        auth_header = f"Bearer {token}"
        mock_request = self._create_mock_request(auth_header=auth_header)
        
        with patch('api_server.middleware.jwt_validator.request', mock_request):
            response, status_code = self.mock_route()
        
        self.assertEqual(status_code, 200)
        self.assertTrue(response['success'])
        self.assertIn('payload', response)
        self.assertEqual(response['payload']['license_key'], self.test_license_key)
        self.assertEqual(response['payload']['ip_address'], self.test_ip)
    
    def test_missing_authorization_header_returns_401(self):
        """Test that missing Authorization header returns 401."""
        mock_request = self._create_mock_request(auth_header=None)
        
        with patch('api_server.middleware.jwt_validator.request', mock_request):
            response, status_code = self.mock_route()
        
        self.assertEqual(status_code, 401)
        self.assertIn('error', response.get_json())
        self.assertEqual(response.get_json()['error'], 'Missing Authorization header')
    
    def test_invalid_authorization_format_returns_401(self):
        """Test that invalid Authorization header format returns 401."""
        # Test without "Bearer" prefix
        token = self._generate_valid_token()
        mock_request = self._create_mock_request(auth_header=token)
        
        with patch('api_server.middleware.jwt_validator.request', mock_request):
            response, status_code = self.mock_route()
        
        self.assertEqual(status_code, 401)
        self.assertIn('error', response.get_json())
        self.assertEqual(response.get_json()['error'], 'Invalid Authorization header format')
    
    def test_malformed_bearer_token_returns_401(self):
        """Test that malformed Bearer token format returns 401."""
        # Test with extra spaces or wrong format
        mock_request = self._create_mock_request(auth_header="Bearer")
        
        with patch('api_server.middleware.jwt_validator.request', mock_request):
            response, status_code = self.mock_route()
        
        self.assertEqual(status_code, 401)
        self.assertIn('error', response.get_json())
    
    def test_expired_token_returns_401(self):
        """Test that expired JWT token returns 401."""
        # Generate token that expired 1 minute ago
        token = self._generate_valid_token(expires_in_minutes=-1)
        auth_header = f"Bearer {token}"
        mock_request = self._create_mock_request(auth_header=auth_header)
        
        with patch('api_server.middleware.jwt_validator.request', mock_request):
            response, status_code = self.mock_route()
        
        self.assertEqual(status_code, 401)
        self.assertIn('error', response.get_json())
        self.assertEqual(response.get_json()['error'], 'Token expired')
    
    def test_invalid_signature_returns_401(self):
        """Test that token with invalid signature returns 401."""
        # Generate token with wrong secret
        current_time = datetime.utcnow()
        expiration_time = current_time + timedelta(minutes=5)
        
        payload = {
            'license_key': self.test_license_key,
            'ip_address': self.test_ip,
            'iat': int(current_time.timestamp()),
            'exp': int(expiration_time.timestamp())
        }
        
        # Sign with wrong secret
        token = jwt.encode(payload, "wrong_secret_key", algorithm='HS256')
        auth_header = f"Bearer {token}"
        mock_request = self._create_mock_request(auth_header=auth_header)
        
        with patch('api_server.middleware.jwt_validator.request', mock_request):
            response, status_code = self.mock_route()
        
        self.assertEqual(status_code, 401)
        self.assertIn('error', response.get_json())
        self.assertEqual(response.get_json()['error'], 'Invalid token')
    
    def test_ip_mismatch_returns_403(self):
        """Test that IP address mismatch returns 403."""
        # Generate token with different IP
        token = self._generate_valid_token(ip_address="10.0.0.1")
        auth_header = f"Bearer {token}"
        # Request comes from different IP
        mock_request = self._create_mock_request(
            auth_header=auth_header,
            remote_addr="192.168.1.100"
        )
        
        with patch('api_server.middleware.jwt_validator.request', mock_request):
            response, status_code = self.mock_route()
        
        self.assertEqual(status_code, 403)
        self.assertIn('error', response.get_json())
        self.assertEqual(response.get_json()['error'], 'IP address mismatch')
    
    def test_token_without_ip_claim_returns_401(self):
        """Test that token without ip_address claim returns 401."""
        # Generate token without ip_address
        current_time = datetime.utcnow()
        expiration_time = current_time + timedelta(minutes=5)
        
        payload = {
            'license_key': self.test_license_key,
            # Missing ip_address
            'iat': int(current_time.timestamp()),
            'exp': int(expiration_time.timestamp())
        }
        
        token = jwt.encode(payload, self.test_secret, algorithm='HS256')
        auth_header = f"Bearer {token}"
        mock_request = self._create_mock_request(auth_header=auth_header)
        
        with patch('api_server.middleware.jwt_validator.request', mock_request):
            response, status_code = self.mock_route()
        
        self.assertEqual(status_code, 401)
        self.assertIn('error', response.get_json())
        self.assertIn('ip_address claim', response.get_json()['message'])
    
    def test_malformed_jwt_returns_401(self):
        """Test that malformed JWT string returns 401."""
        auth_header = "Bearer not.a.valid.jwt.token"
        mock_request = self._create_mock_request(auth_header=auth_header)
        
        with patch('api_server.middleware.jwt_validator.request', mock_request):
            response, status_code = self.mock_route()
        
        self.assertEqual(status_code, 401)
        self.assertIn('error', response.get_json())
        self.assertEqual(response.get_json()['error'], 'Invalid token')
    
    def test_jwt_payload_passed_to_route_handler(self):
        """Test that decoded JWT payload is passed to the route handler."""
        token = self._generate_valid_token()
        auth_header = f"Bearer {token}"
        mock_request = self._create_mock_request(auth_header=auth_header)
        
        with patch('api_server.middleware.jwt_validator.request', mock_request):
            response, status_code = self.mock_route()
        
        self.assertEqual(status_code, 200)
        payload = response['payload']
        
        # Verify all required claims are present
        self.assertIn('license_key', payload)
        self.assertIn('ip_address', payload)
        self.assertIn('iat', payload)
        self.assertIn('exp', payload)
        
        # Verify claim values
        self.assertEqual(payload['license_key'], self.test_license_key)
        self.assertEqual(payload['ip_address'], self.test_ip)
    
    def test_case_insensitive_bearer_prefix(self):
        """Test that Bearer prefix is case-insensitive."""
        token = self._generate_valid_token()
        
        # Test with lowercase "bearer"
        auth_header = f"bearer {token}"
        mock_request = self._create_mock_request(auth_header=auth_header)
        
        with patch('api_server.middleware.jwt_validator.request', mock_request):
            response, status_code = self.mock_route()
        
        self.assertEqual(status_code, 200)
        self.assertTrue(response['success'])
    
    def test_ipv6_address_validation(self):
        """Test that IPv6 addresses are validated correctly."""
        ipv6_address = "2001:0db8:85a3:0000:0000:8a2e:0370:7334"
        token = self._generate_valid_token(ip_address=ipv6_address)
        auth_header = f"Bearer {token}"
        mock_request = self._create_mock_request(
            auth_header=auth_header,
            remote_addr=ipv6_address
        )
        
        with patch('api_server.middleware.jwt_validator.request', mock_request):
            response, status_code = self.mock_route()
        
        self.assertEqual(status_code, 200)
        self.assertTrue(response['success'])
        self.assertEqual(response['payload']['ip_address'], ipv6_address)
    
    def test_multiple_spaces_in_authorization_header(self):
        """Test that multiple spaces in Authorization header are handled."""
        token = self._generate_valid_token()
        auth_header = f"Bearer  {token}  extra"  # Multiple spaces and extra text
        mock_request = self._create_mock_request(auth_header=auth_header)
        
        with patch('api_server.middleware.jwt_validator.request', mock_request):
            response, status_code = self.mock_route()
        
        # Should fail because format is invalid (more than 2 parts)
        self.assertEqual(status_code, 401)
        self.assertIn('error', response.get_json())


if __name__ == '__main__':
    unittest.main()
