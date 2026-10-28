"""
Basic integration tests for admin endpoints.

These tests verify that the admin endpoints are working correctly
with the database and license service.
"""

import pytest
from datetime import datetime, timedelta
from flask import Flask

from ..app import create_app
from ..database import init_db, close_db, db_pool
from ..models import License, Session


@pytest.fixture(scope='module')
def app():
    """Create Flask app for testing."""
    # Use test configuration
    test_config = {
        'TESTING': True,
        'DATABASE_URL': 'postgresql://postgres:postgres@localhost:5432/cipher_test',
        'ADMIN_TOKEN': 'test-admin-token',
        'ADMIN_REQUIRE_TOKEN': True,
        'ADMIN_LOCALHOST_ONLY': False,
    }
    
    app = create_app(test_config)
    
    # Initialize database
    init_db(test_config['DATABASE_URL'])
    
    yield app
    
    # Cleanup
    close_db()


@pytest.fixture(scope='module')
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture(scope='module')
def admin_headers():
    """Authorization headers for admin-protected endpoints."""
    return {'Authorization': 'Bearer test-admin-token'}


@pytest.fixture(autouse=True)
def cleanup_database():
    """Clean up database before each test."""
    yield
    # Clean up after test
    try:
        with db_pool.get_cursor(commit=True) as cursor:
            cursor.execute("DELETE FROM sessions")
            cursor.execute("DELETE FROM licenses")
    except:
        pass


def test_create_license_success(client, admin_headers):
    """Test creating a license with valid parameters."""
    # Prepare request data
    expires_at = (datetime.utcnow() + timedelta(days=30)).isoformat() + 'Z'
    data = {
        'expires_at': expires_at,
        'max_sessions': 2,
        'note': 'Test customer'
    }
    
    # Send request
    response = client.post('/admin/license/create', json=data, headers=admin_headers)
    
    # Verify response
    assert response.status_code == 200
    json_data = response.get_json()
    
    assert 'license_key' in json_data
    assert len(json_data['license_key']) == 25
    assert json_data['status'] == 'active'
    assert json_data['max_sessions'] == 2
    assert json_data['note'] == 'Test customer'


def test_admin_endpoint_rejects_missing_token(client):
    """Admin endpoints must reject requests without Authorization header."""
    expires_at = (datetime.utcnow() + timedelta(days=30)).isoformat() + 'Z'
    data = {
        'expires_at': expires_at,
        'max_sessions': 1,
        'note': 'Unauthorized test'
    }

    response = client.post('/admin/license/create', json=data)
    assert response.status_code == 401


def test_create_license_missing_expires_at(client, admin_headers):
    """Test creating a license without expires_at."""
    data = {
        'max_sessions': 1
    }
    
    response = client.post('/admin/license/create', json=data, headers=admin_headers)
    
    assert response.status_code == 400
    json_data = response.get_json()
    assert 'error' in json_data


def test_create_license_invalid_max_sessions(client, admin_headers):
    """Test creating a license with invalid max_sessions."""
    expires_at = (datetime.utcnow() + timedelta(days=30)).isoformat() + 'Z'
    data = {
        'expires_at': expires_at,
        'max_sessions': 0  # Invalid
    }
    
    response = client.post('/admin/license/create', json=data, headers=admin_headers)
    
    assert response.status_code == 400
    json_data = response.get_json()
    assert 'error' in json_data


def test_extend_license_success(client, admin_headers):
    """Test extending a license."""
    # First create a license
    expires_at = (datetime.utcnow() + timedelta(days=30)).isoformat() + 'Z'
    create_data = {
        'expires_at': expires_at,
        'max_sessions': 1,
        'note': 'Test'
    }
    
    create_response = client.post('/admin/license/create', json=create_data, headers=admin_headers)
    assert create_response.status_code == 200
    license_key = create_response.get_json()['license_key']
    
    # Now extend it
    new_expires_at = (datetime.utcnow() + timedelta(days=60)).isoformat() + 'Z'
    extend_data = {
        'license_key': license_key,
        'new_expires_at': new_expires_at
    }
    
    response = client.post('/admin/license/extend', json=extend_data, headers=admin_headers)
    
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['message'] == 'License extended'
    assert 'expires_at' in json_data


def test_extend_license_not_found(client, admin_headers):
    """Test extending a non-existent license."""
    new_expires_at = (datetime.utcnow() + timedelta(days=60)).isoformat() + 'Z'
    data = {
        'license_key': 'NONEXISTENT12345678901234',
        'new_expires_at': new_expires_at
    }
    
    response = client.post('/admin/license/extend', json=data, headers=admin_headers)
    
    assert response.status_code == 404
    json_data = response.get_json()
    assert 'error' in json_data


def test_list_licenses_no_filter(client, admin_headers):
    """Test listing all licenses without filter."""
    # Create a few licenses
    for i in range(3):
        expires_at = (datetime.utcnow() + timedelta(days=30)).isoformat() + 'Z'
        data = {
            'expires_at': expires_at,
            'max_sessions': 1,
            'note': f'Test {i}'
        }
        client.post('/admin/license/create', json=data, headers=admin_headers)
    
    # List licenses
    response = client.get('/admin/licenses', headers=admin_headers)
    
    assert response.status_code == 200
    json_data = response.get_json()
    
    assert 'licenses' in json_data
    assert 'total' in json_data
    assert len(json_data['licenses']) >= 3
    
    # Verify each license has active_sessions field
    for license_data in json_data['licenses']:
        assert 'active_sessions' in license_data


def test_list_licenses_with_status_filter(client, admin_headers):
    """Test listing licenses with status filter."""
    # Create an active license
    expires_at = (datetime.utcnow() + timedelta(days=30)).isoformat() + 'Z'
    data = {
        'expires_at': expires_at,
        'max_sessions': 1,
        'note': 'Active test'
    }
    client.post('/admin/license/create', json=data, headers=admin_headers)
    
    # List active licenses
    response = client.get('/admin/licenses?status=active', headers=admin_headers)
    
    assert response.status_code == 200
    json_data = response.get_json()
    
    assert 'licenses' in json_data
    # All returned licenses should be active
    for license_data in json_data['licenses']:
        assert license_data['status'] == 'active'


def test_list_licenses_with_pagination(client, admin_headers):
    """Test listing licenses with pagination."""
    response = client.get('/admin/licenses?limit=10&offset=0', headers=admin_headers)
    
    assert response.status_code == 200
    json_data = response.get_json()
    
    assert json_data['limit'] == 10
    assert json_data['offset'] == 0


def test_list_sessions_no_filter(client, admin_headers):
    """Test listing all sessions."""
    response = client.get('/admin/sessions', headers=admin_headers)
    
    assert response.status_code == 200
    json_data = response.get_json()
    
    assert 'sessions' in json_data
    assert isinstance(json_data['sessions'], list)


def test_list_sessions_with_license_filter(client, admin_headers):
    """Test listing sessions for a specific license."""
    # Create a license
    expires_at = (datetime.utcnow() + timedelta(days=30)).isoformat() + 'Z'
    data = {
        'expires_at': expires_at,
        'max_sessions': 1,
        'note': 'Session test'
    }
    
    create_response = client.post('/admin/license/create', json=data, headers=admin_headers)
    license_key = create_response.get_json()['license_key']
    
    # List sessions for this license
    response = client.get(f'/admin/sessions?license_key={license_key}', headers=admin_headers)
    
    assert response.status_code == 200
    json_data = response.get_json()
    
    assert 'sessions' in json_data


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
