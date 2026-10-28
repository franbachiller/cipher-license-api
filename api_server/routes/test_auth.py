"""
Unit tests for authentication endpoint.

Tests the POST /api/auth endpoint implementation covering:
- Valid license authentication
- Invalid license key format
- Non-existent license key
- Expired license
- Revoked license
- Session limit reached
"""

import pytest
import json
from datetime import datetime, timedelta
import hashlib

from ..app import create_app
from ..database import init_db, close_db, db_pool
from ..models import License, Session
from ..config import Config


@pytest.fixture
def app():
    """Create test Flask application."""
    test_config = {
        'TESTING': True,
        'DATABASE_URL': 'postgresql://cipher_user:cipher_pass@localhost:5432/cipher_license_test'
    }
    app = create_app(test_config)
    
    # Initialize test database
    init_db(test_config['DATABASE_URL'])
    
    yield app
    
    # Cleanup
    close_db()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def setup_test_data():
    """Setup test data in database."""
    with db_pool.get_cursor(commit=True) as cursor:
        # Clean up existing test data
        cursor.execute("DELETE FROM sessions")
        cursor.execute("DELETE FROM licenses")
        
        # Create test licenses
        # Active license with future expiration
        cursor.execute(
            """
            INSERT INTO licenses (key, status, expires_at, max_sessions, note)
            VALUES (%s, 'active', %s, %s, %s)
            """,
            ('ACTIVE1234567890ABCDEFGHI', datetime.utcnow() + timedelta(days=30), 2, 'Test active license')
        )
        
        # Expired license
        cursor.execute(
            """
            INSERT INTO licenses (key, status, expires_at, max_sessions, note)
            VALUES (%s, 'active', %s, %s, %s)
            """,
            ('EXPIRED123456789ABCDEFGHI', datetime.utcnow() - timedelta(days=1), 1, 'Test expired license')
        )
        
        # Revoked license
        cursor.execute(
            """
            INSERT INTO licenses (key, status, expires_at, max_sessions, note)
            VALUES (%s, 'revoked', %s, %s, %s)
            """,
            ('REVOKED123456789ABCDEFGHI', datetime.utcnow() + timedelta(days=30), 1, 'Test revoked license')
        )
        
        # License with session limit of 1
        cursor.execute(
            """
            INSERT INTO licenses (key, status, expires_at, max_sessions, note)
            VALUES (%s, 'active', %s, %s, %s)
            """,
            ('LIMITED123456789ABCDEFGHI', datetime.utcnow() + timedelta(days=30), 1, 'Test limited license')
        )
        
        # Create an active session for the limited license
        cursor.execute(
            """
            INSERT INTO sessions (license_key, jwt_token_hash, ip_address, expires_at)
            VALUES (%s, %s, %s, %s)
            """,
            ('LIMITED123456789ABCDEFGHI', hashlib.sha256(b'test_token').hexdigest(), '127.0.0.1', datetime.utcnow() + timedelta(minutes=5))
        )
    
    yield
    
    # Cleanup after test
    with db_pool.get_cursor(commit=True) as cursor:
        cursor.execute("DELETE FROM sessions")
        cursor.execute("DELETE FROM licenses")


def test_auth_valid_license(client, setup_test_data):
    """Test authentication with valid license key."""
    response = client.post(
        '/api/auth',
        data=json.dumps({'license_key': 'ACTIVE1234567890ABCDEFGHI'}),
        content_type='application/json'
    )
    
    assert response.status_code == 200
    data = json.loads(response.data)
    
    assert 'jwt_token' in data
    assert 'expires_at' in data
    assert 'message' in data
    assert data['message'] == 'Authentication successful'
    
    # Verify JWT token is not empty
    assert len(data['jwt_token']) > 0
    
    # Verify expires_at is in ISO format
    assert 'T' in data['expires_at']
    assert data['expires_at'].endswith('Z')


def test_auth_invalid_request_format(client, setup_test_data):
    """Test authentication with invalid request format."""
    # Missing license_key field
    response = client.post(
        '/api/auth',
        data=json.dumps({}),
        content_type='application/json'
    )
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data
    assert data['error'] == 'Invalid request format'


def test_auth_invalid_key_format(client, setup_test_data):
    """Test authentication with malformed license key."""
    # Too short
    response = client.post(
        '/api/auth',
        data=json.dumps({'license_key': 'SHORT'}),
        content_type='application/json'
    )
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data
    assert 'format' in data['error'].lower()
    
    # Invalid characters
    response = client.post(
        '/api/auth',
        data=json.dumps({'license_key': 'INVALID@#$%^&*()1234567'}),
        content_type='application/json'
    )
    
    assert response.status_code == 400


def test_auth_nonexistent_license(client, setup_test_data):
    """Test authentication with non-existent license key."""
    response = client.post(
        '/api/auth',
        data=json.dumps({'license_key': 'NONEXIST1234567890ABCDEFG'}),
        content_type='application/json'
    )
    
    assert response.status_code == 401
    data = json.loads(response.data)
    assert 'error' in data
    assert data['error'] == 'Invalid license key'


def test_auth_expired_license(client, setup_test_data):
    """Test authentication with expired license."""
    response = client.post(
        '/api/auth',
        data=json.dumps({'license_key': 'EXPIRED123456789ABCDEFGHI'}),
        content_type='application/json'
    )
    
    assert response.status_code == 403
    data = json.loads(response.data)
    assert 'error' in data
    assert 'expired' in data['error'].lower()


def test_auth_revoked_license(client, setup_test_data):
    """Test authentication with revoked license."""
    response = client.post(
        '/api/auth',
        data=json.dumps({'license_key': 'REVOKED123456789ABCDEFGHI'}),
        content_type='application/json'
    )
    
    assert response.status_code == 403
    data = json.loads(response.data)
    assert 'error' in data
    assert 'revoked' in data['error'].lower()


def test_auth_relogin_replaces_existing_session(client, setup_test_data):
    """A new login replaces the license's previous session instead of being rejected."""
    # LIMITED has max_sessions = 1 and already holds an active session.
    response = client.post(
        '/api/auth',
        data=json.dumps({'license_key': 'LIMITED123456789ABCDEFGHI'}),
        content_type='application/json'
    )

    assert response.status_code == 200
    with db_pool.get_cursor() as cursor:
        cursor.execute(
            "SELECT jwt_token_hash FROM sessions WHERE license_key = %s",
            ('LIMITED123456789ABCDEFGHI',)
        )
        rows = cursor.fetchall()
    assert len(rows) == 1
    assert rows[0]['jwt_token_hash'] != hashlib.sha256(b'test_token').hexdigest()


def test_auth_creates_session_record(client, setup_test_data):
    """Test that authentication creates a session record in database."""
    # Get initial session count
    with db_pool.get_cursor() as cursor:
        cursor.execute("SELECT COUNT(*) as count FROM sessions WHERE license_key = %s", ('ACTIVE1234567890ABCDEFGHI',))
        initial_count = cursor.fetchone()['count']
    
    # Authenticate
    response = client.post(
        '/api/auth',
        data=json.dumps({'license_key': 'ACTIVE1234567890ABCDEFGHI'}),
        content_type='application/json'
    )
    
    assert response.status_code == 200
    
    # Verify session was created
    with db_pool.get_cursor() as cursor:
        cursor.execute("SELECT COUNT(*) as count FROM sessions WHERE license_key = %s", ('ACTIVE1234567890ABCDEFGHI',))
        final_count = cursor.fetchone()['count']
    
    assert final_count == initial_count + 1


def test_auth_stores_jwt_hash(client, setup_test_data):
    """Test that JWT token is hashed before storage."""
    response = client.post(
        '/api/auth',
        data=json.dumps({'license_key': 'ACTIVE1234567890ABCDEFGHI'}),
        content_type='application/json'
    )
    
    assert response.status_code == 200
    data = json.loads(response.data)
    jwt_token = data['jwt_token']
    
    # Calculate expected hash
    expected_hash = hashlib.sha256(jwt_token.encode()).hexdigest()
    
    # Verify hash is stored in database
    with db_pool.get_cursor() as cursor:
        cursor.execute(
            "SELECT jwt_token_hash FROM sessions WHERE license_key = %s ORDER BY created_at DESC LIMIT 1",
            ('ACTIVE1234567890ABCDEFGHI',)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row['jwt_token_hash'] == expected_hash


def test_auth_repeated_logins_keep_single_session(client, setup_test_data):
    """Repeated logins with the same license always succeed and keep one active session."""
    for _ in range(3):
        response = client.post(
            '/api/auth',
            data=json.dumps({'license_key': 'ACTIVE1234567890ABCDEFGHI'}),
            content_type='application/json'
        )
        assert response.status_code == 200

    with db_pool.get_cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) as count FROM sessions WHERE license_key = %s",
            ('ACTIVE1234567890ABCDEFGHI',)
        )
        assert cursor.fetchone()['count'] == 1
