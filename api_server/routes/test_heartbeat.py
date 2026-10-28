"""
Unit tests for heartbeat endpoint.

These tests verify that the heartbeat endpoint correctly updates session
timestamps and handles various error conditions.

Requirements: 3.2, 3.3
"""

import pytest
import hashlib
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from api_server.app import create_app
from api_server.database import db_pool
from api_server.utils.jwt_utils import generate_jwt_token


def _valid_token():
    """Real JWT bound to the Flask test client's address."""
    return generate_jwt_token('ABCD1234EFGH5678IJKL90MNO', '127.0.0.1')


@pytest.fixture
def app():
    """Create test Flask application."""
    # Mock database initialization to avoid requiring actual database
    with patch('api_server.app.init_db'):
        with patch('api_server.app.start_cleanup_task'):
            app = create_app({
                'TESTING': True,
                'SECRET_KEY': 'test-secret-key',
                'JWT_SECRET_KEY': 'test-jwt-secret',
                'DATABASE_URL': 'postgresql://test:test@localhost/test'
            })
            yield app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def mock_jwt_payload():
    """Mock JWT payload for testing."""
    return {
        'license_key': 'ABCD1234EFGH5678IJKL90MNO',
        'ip_address': '192.168.1.100',
        'iat': datetime.utcnow().timestamp(),
        'exp': (datetime.utcnow() + timedelta(minutes=5)).timestamp()
    }


def test_heartbeat_with_valid_jwt_updates_timestamp(client, mock_jwt_payload):
    """
    Test that heartbeat with valid JWT updates last_seen timestamp.
    
    Requirements: 3.2, 3.3
    """
    # Mock JWT validation to pass
    with patch('api_server.routes.heartbeat.require_jwt_auth') as mock_auth:
        # Configure decorator to pass through and inject payload
        def mock_decorator(f):
            def wrapper(*args, **kwargs):
                return f(jwt_payload=mock_jwt_payload, *args, **kwargs)
            wrapper.__name__ = f.__name__
            return wrapper
        mock_auth.side_effect = mock_decorator
        
        # Mock database operations
        with patch('api_server.routes.heartbeat.db_pool.get_cursor') as mock_cursor:
            mock_cursor_obj = MagicMock()
            mock_cursor.__enter__ = Mock(return_value=mock_cursor_obj)
            mock_cursor.__exit__ = Mock(return_value=False)
            
            # Mock Session.update_heartbeat to return True (success)
            with patch('api_server.routes.heartbeat.Session.update_heartbeat', return_value=True):
                # Send heartbeat request
                response = client.post(
                    '/api/heartbeat',
                    headers={'Authorization': f'Bearer {_valid_token()}'}
                )
                
                # Verify response
                assert response.status_code == 200
                data = response.get_json()
                assert data['status'] == 'alive'
                assert data['next_heartbeat'] == 30


def test_heartbeat_with_nonexistent_session_returns_404(client, mock_jwt_payload):
    """
    Test that heartbeat for non-existent session returns 404.
    
    Requirements: 3.3
    """
    with patch('api_server.routes.heartbeat.require_jwt_auth') as mock_auth:
        def mock_decorator(f):
            def wrapper(*args, **kwargs):
                return f(jwt_payload=mock_jwt_payload, *args, **kwargs)
            wrapper.__name__ = f.__name__
            return wrapper
        mock_auth.side_effect = mock_decorator
        
        with patch('api_server.routes.heartbeat.db_pool.get_cursor') as mock_cursor:
            mock_cursor_obj = MagicMock()
            mock_cursor.__enter__ = Mock(return_value=mock_cursor_obj)
            mock_cursor.__exit__ = Mock(return_value=False)
            
            # Mock Session.update_heartbeat to return False (not found)
            with patch('api_server.routes.heartbeat.Session.update_heartbeat', return_value=False):
                response = client.post(
                    '/api/heartbeat',
                    headers={'Authorization': f'Bearer {_valid_token()}'}
                )
                
                assert response.status_code == 404
                data = response.get_json()
                assert 'error' in data
                assert data['error'] == 'Session not found'


def test_heartbeat_without_jwt_returns_401(client):
    """
    Test that heartbeat without JWT token returns 401.
    
    Requirements: 3.2
    """
    # Don't mock JWT validation - let it fail naturally
    response = client.post('/api/heartbeat')
    
    assert response.status_code == 401
    data = response.get_json()
    assert 'error' in data


def test_heartbeat_computes_jwt_hash_correctly(client, mock_jwt_payload):
    """
    Test that heartbeat correctly computes SHA-256 hash of JWT token.
    
    Requirements: 3.3
    """
    test_token = _valid_token()
    expected_hash = hashlib.sha256(test_token.encode()).hexdigest()
    
    with patch('api_server.routes.heartbeat.require_jwt_auth') as mock_auth:
        def mock_decorator(f):
            def wrapper(*args, **kwargs):
                return f(jwt_payload=mock_jwt_payload, *args, **kwargs)
            wrapper.__name__ = f.__name__
            return wrapper
        mock_auth.side_effect = mock_decorator
        
        with patch('api_server.routes.heartbeat.db_pool.get_cursor') as mock_cursor:
            mock_cursor_obj = MagicMock()
            mock_cursor.__enter__ = Mock(return_value=mock_cursor_obj)
            mock_cursor.__exit__ = Mock(return_value=False)
            
            # Capture the hash passed to update_heartbeat
            captured_hash = None
            def capture_hash(cursor, jwt_hash):
                nonlocal captured_hash
                captured_hash = jwt_hash
                return True
            
            with patch('api_server.routes.heartbeat.Session.update_heartbeat', side_effect=capture_hash):
                response = client.post(
                    '/api/heartbeat',
                    headers={'Authorization': f'Bearer {test_token}'}
                )
                
                assert response.status_code == 200
                assert captured_hash == expected_hash


def test_heartbeat_handles_database_errors_gracefully(client, mock_jwt_payload):
    """
    Test that heartbeat handles database errors gracefully.
    
    Requirements: 3.3
    """
    with patch('api_server.routes.heartbeat.require_jwt_auth') as mock_auth:
        def mock_decorator(f):
            def wrapper(*args, **kwargs):
                return f(jwt_payload=mock_jwt_payload, *args, **kwargs)
            wrapper.__name__ = f.__name__
            return wrapper
        mock_auth.side_effect = mock_decorator
        
        # Mock database to raise exception
        with patch('api_server.routes.heartbeat.db_pool.get_cursor') as mock_cursor:
            mock_cursor.side_effect = Exception("Database connection failed")
            
            response = client.post(
                '/api/heartbeat',
                headers={'Authorization': f'Bearer {_valid_token()}'}
            )
            
            assert response.status_code == 500
            data = response.get_json()
            assert 'error' in data
            assert data['error'] == 'Internal server error'
