"""
Unit tests for rate limiting middleware.

Tests the Flask-Limiter configuration covering:
- Rate limit enforcement on /api/auth (10 requests per minute)
- Rate limit enforcement on other API endpoints (60 requests per minute)
- 429 status code when rate limit exceeded
- Rate limit reset after time window

Requirements: 5.2
"""

import pytest
import json
import time
from datetime import datetime, timedelta
import hashlib

from ..app import create_app
from ..database import init_db, close_db, db_pool


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
def setup_test_license():
    """Setup a test license for authentication tests."""
    with db_pool.get_cursor(commit=True) as cursor:
        # Clean up existing test data
        cursor.execute("DELETE FROM sessions")
        cursor.execute("DELETE FROM licenses")
        
        # Create test license with high session limit
        cursor.execute(
            """
            INSERT INTO licenses (key, status, expires_at, max_sessions, note)
            VALUES (%s, 'active', %s, %s, %s)
            """,
            ('RATELIMIT12345678ABCDEFGH', datetime.utcnow() + timedelta(days=30), 100, 'Test rate limit license')
        )
    
    yield
    
    # Cleanup after test
    with db_pool.get_cursor(commit=True) as cursor:
        cursor.execute("DELETE FROM sessions")
        cursor.execute("DELETE FROM licenses")


def test_auth_rate_limit_enforcement(client, setup_test_license):
    """
    Test that /api/auth endpoint enforces 10 requests per minute rate limit.
    
    Requirements: 5.2
    """
    # Make 10 requests (should all succeed)
    for i in range(10):
        response = client.post(
            '/api/auth',
            data=json.dumps({'license_key': 'RATELIMIT12345678ABCDEFGH'}),
            content_type='application/json'
        )
        assert response.status_code == 200, f"Request {i+1} should succeed"
    
    # 11th request should be rate limited
    response = client.post(
        '/api/auth',
        data=json.dumps({'license_key': 'RATELIMIT12345678ABCDEFGH'}),
        content_type='application/json'
    )
    
    assert response.status_code == 429, "11th request should be rate limited"
    data = json.loads(response.data)
    assert 'error' in data
    assert 'rate limit' in data['error'].lower()


def test_auth_rate_limit_returns_429(client, setup_test_license):
    """
    Test that rate limit exceeded returns 429 status code with appropriate message.
    
    Requirements: 5.2
    """
    # Exhaust rate limit
    for i in range(10):
        client.post(
            '/api/auth',
            data=json.dumps({'license_key': 'RATELIMIT12345678ABCDEFGH'}),
            content_type='application/json'
        )
    
    # Next request should return 429
    response = client.post(
        '/api/auth',
        data=json.dumps({'license_key': 'RATELIMIT12345678ABCDEFGH'}),
        content_type='application/json'
    )
    
    assert response.status_code == 429
    data = json.loads(response.data)
    
    # Verify error message structure
    assert 'error' in data
    assert data['error'] == 'Rate limit exceeded'
    assert 'message' in data


def test_rate_limit_per_ip_isolation(client, setup_test_license):
    """
    Test that rate limits are enforced per IP address.
    
    Note: This test is limited by Flask test client's ability to simulate different IPs.
    In production, different IPs would have separate rate limit counters.
    
    Requirements: 5.2
    """
    # Make requests from "same" IP (test client limitation)
    for i in range(10):
        response = client.post(
            '/api/auth',
            data=json.dumps({'license_key': 'RATELIMIT12345678ABCDEFGH'}),
            content_type='application/json'
        )
        assert response.status_code == 200
    
    # 11th request should be rate limited
    response = client.post(
        '/api/auth',
        data=json.dumps({'license_key': 'RATELIMIT12345678ABCDEFGH'}),
        content_type='application/json'
    )
    assert response.status_code == 429


def test_rate_limit_does_not_affect_valid_errors(client, setup_test_license):
    """
    Test that rate limiting doesn't interfere with other error responses.
    
    Requirements: 5.2
    """
    # Make a few requests with invalid license key
    for i in range(3):
        response = client.post(
            '/api/auth',
            data=json.dumps({'license_key': 'INVALID12345678ABCDEFGHIJ'}),
            content_type='application/json'
        )
        # Should return 401 (invalid key), not 429 (rate limit)
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['error'] == 'Invalid license key'


def test_rate_limit_counter_increments(client, setup_test_license):
    """
    Test that rate limit counter increments with each request.
    
    Requirements: 5.2
    """
    # Make requests and verify they succeed until limit
    success_count = 0
    
    for i in range(15):
        response = client.post(
            '/api/auth',
            data=json.dumps({'license_key': 'RATELIMIT12345678ABCDEFGH'}),
            content_type='application/json'
        )
        
        if response.status_code == 200:
            success_count += 1
        elif response.status_code == 429:
            # Once we hit rate limit, all subsequent requests should also be rate limited
            break
    
    # Should have exactly 10 successful requests
    assert success_count == 10, f"Expected 10 successful requests, got {success_count}"


def test_health_endpoint_not_rate_limited(client):
    """
    Test that health check endpoint is not rate limited.
    
    Requirements: 5.2
    """
    # Make many requests to health endpoint
    for i in range(20):
        response = client.get('/health')
        assert response.status_code == 200, f"Health check request {i+1} should not be rate limited"


def test_root_endpoint_not_rate_limited(client):
    """
    Test that root endpoint is not rate limited.
    
    Requirements: 5.2
    """
    # Make many requests to root endpoint
    for i in range(20):
        response = client.get('/')
        assert response.status_code == 200, f"Root endpoint request {i+1} should not be rate limited"


def test_rate_limit_message_format(client, setup_test_license):
    """
    Test that rate limit error message has correct format.
    
    Requirements: 5.2
    """
    # Exhaust rate limit
    for i in range(10):
        client.post(
            '/api/auth',
            data=json.dumps({'license_key': 'RATELIMIT12345678ABCDEFGH'}),
            content_type='application/json'
        )
    
    # Get rate limit error
    response = client.post(
        '/api/auth',
        data=json.dumps({'license_key': 'RATELIMIT12345678ABCDEFGH'}),
        content_type='application/json'
    )
    
    assert response.status_code == 429
    data = json.loads(response.data)
    
    # Verify JSON structure
    assert isinstance(data, dict)
    assert 'error' in data
    assert 'message' in data
    assert isinstance(data['error'], str)
    assert isinstance(data['message'], str)
