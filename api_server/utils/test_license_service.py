"""
Unit tests for license service CRUD operations.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, Mock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))


from api_server.utils import license_service
from api_server.utils.license_service import create_license, revoke_license, extend_license, list_licenses
from api_server.models import License, Session


class TestCreateLicense:
    """Tests for license creation."""
    
    def test_create_license_with_valid_parameters(self):
        """Test that license creation with valid parameters succeeds."""
        expires_at = datetime.utcnow() + timedelta(days=30)
        
        mock_license = MagicMock()
        mock_license.key = "ABCD1234EFGH5678IJKL90MNO"
        mock_license.status = "active"
        mock_license.expires_at = expires_at
        mock_license.max_sessions = 2
        mock_license.created_at = datetime.utcnow()
        mock_license.note = "Test customer"
        
        with patch.object(license_service, 'generate_license_key', return_value="ABCD1234EFGH5678IJKL90MNO"):
            with patch.object(license_service, 'db_pool') as mock_pool:
                mock_ctx = MagicMock()
                mock_pool.get_cursor.return_value.__enter__.return_value = mock_ctx
                
                with patch.object(License, 'create', return_value=mock_license):
                    result = license_service.create_license(expires_at, max_sessions=2, note="Test customer")
                    
                    assert result['license_key'] == "ABCD1234EFGH5678IJKL90MNO"
                    assert result['status'] == "active"
                    assert result['max_sessions'] == 2
                    assert result['note'] == "Test customer"
    
    def test_create_license_with_default_max_sessions(self):
        """Test that license creation defaults to max_sessions=1."""
        expires_at = datetime.utcnow() + timedelta(days=30)
        
        mock_license = MagicMock()
        mock_license.key = "TESTKEY12345678901234567"
        mock_license.status = "active"
        mock_license.expires_at = expires_at
        mock_license.max_sessions = 1
        mock_license.created_at = datetime.utcnow()
        mock_license.note = ""
        
        with patch('api_server.utils.license_service.generate_license_key', return_value="TESTKEY12345678901234567"):
            with patch('api_server.utils.license_service.db_pool.get_cursor') as mock_cursor:
                mock_ctx = MagicMock()
                mock_cursor.return_value.__enter__.return_value = mock_ctx
                
                with patch('api_server.utils.license_service.License.create', return_value=mock_license):
                    result = create_license(expires_at)
                    
                    assert result['max_sessions'] == 1
    
    def test_create_license_with_invalid_max_sessions(self):
        """Test that license creation with max_sessions < 1 raises ValueError."""
        expires_at = datetime.utcnow() + timedelta(days=30)
        
        with pytest.raises(ValueError, match="max_sessions must be at least 1"):
            create_license(expires_at, max_sessions=0)
    
    def test_create_license_generates_unique_key(self):
        """Test that license creation generates a unique key."""
        expires_at = datetime.utcnow() + timedelta(days=30)
        
        mock_license = MagicMock()
        mock_license.key = "UNIQUEKEY1234567890123456"
        mock_license.status = "active"
        mock_license.expires_at = expires_at
        mock_license.max_sessions = 1
        mock_license.created_at = datetime.utcnow()
        mock_license.note = ""
        
        with patch('api_server.utils.license_service.generate_license_key', return_value="UNIQUEKEY1234567890123456") as mock_gen:
            with patch('api_server.utils.license_service.db_pool.get_cursor') as mock_cursor:
                mock_ctx = MagicMock()
                mock_cursor.return_value.__enter__.return_value = mock_ctx
                
                with patch('api_server.utils.license_service.License.create', return_value=mock_license):
                    result = create_license(expires_at)
                    
                    # Verify generate_license_key was called
                    mock_gen.assert_called_once()
                    assert result['license_key'] == "UNIQUEKEY1234567890123456"


class TestRevokeLicense:
    """Tests for license revocation."""
    
    def test_revoke_license_updates_status_correctly(self):
        """Test that revoking a license updates status to 'revoked'."""
        license_key = "ABCD1234EFGH5678IJKL90MNO"
        
        mock_license = MagicMock()
        mock_license.key = license_key
        mock_license.status = "active"
        
        with patch('api_server.utils.license_service.db_pool.get_cursor') as mock_cursor:
            mock_ctx = MagicMock()
            mock_cursor.return_value.__enter__.return_value = mock_ctx
            
            with patch('api_server.utils.license_service.License.find_by_key', return_value=mock_license):
                with patch('api_server.utils.license_service.License.update_status') as mock_update:
                    with patch('api_server.utils.license_service.Session.delete_by_license_key', return_value=0):
                        result = revoke_license(license_key)
                        
                        # Verify update_status was called with 'revoked'
                        mock_update.assert_called_once_with(mock_ctx, license_key, 'revoked')
                        assert result['message'] == 'License revoked'
    
    def test_revoke_license_terminates_sessions(self):
        """Test that revoking a license terminates all active sessions."""
        license_key = "ABCD1234EFGH5678IJKL90MNO"
        
        mock_license = MagicMock()
        mock_license.key = license_key
        
        with patch('api_server.utils.license_service.db_pool.get_cursor') as mock_cursor:
            mock_ctx = MagicMock()
            mock_cursor.return_value.__enter__.return_value = mock_ctx
            
            with patch('api_server.utils.license_service.License.find_by_key', return_value=mock_license):
                with patch('api_server.utils.license_service.License.update_status'):
                    with patch('api_server.utils.license_service.Session.delete_by_license_key', return_value=3) as mock_delete:
                        result = revoke_license(license_key)
                        
                        # Verify sessions were deleted
                        mock_delete.assert_called_once_with(mock_ctx, license_key)
                        assert result['sessions_terminated'] == 3
    
    def test_revoke_license_with_nonexistent_key(self):
        """Test that revoking a non-existent license raises ValueError."""
        license_key = "NONEXISTENT12345678901234"
        
        with patch('api_server.utils.license_service.db_pool.get_cursor') as mock_cursor:
            mock_ctx = MagicMock()
            mock_cursor.return_value.__enter__.return_value = mock_ctx
            
            with patch('api_server.utils.license_service.License.find_by_key', return_value=None):
                with pytest.raises(ValueError, match="License key not found"):
                    revoke_license(license_key)


class TestExtendLicense:
    """Tests for license extension."""
    
    def test_extend_license_updates_expires_at(self):
        """Test that extending a license updates the expiration date."""
        license_key = "ABCD1234EFGH5678IJKL90MNO"
        new_expires_at = datetime.utcnow() + timedelta(days=60)
        
        mock_license = MagicMock()
        mock_license.key = license_key
        
        with patch('api_server.utils.license_service.db_pool.get_cursor') as mock_cursor:
            mock_ctx = MagicMock()
            mock_cursor.return_value.__enter__.return_value = mock_ctx
            
            with patch('api_server.utils.license_service.License.find_by_key', return_value=mock_license):
                with patch('api_server.utils.license_service.License.update_expires_at') as mock_update:
                    result = extend_license(license_key, new_expires_at)
                    
                    # Verify update_expires_at was called with correct parameters
                    mock_update.assert_called_once_with(mock_ctx, license_key, new_expires_at)
                    assert result['message'] == 'License extended'
                    assert result['expires_at'] == new_expires_at.isoformat()
    
    def test_extend_license_with_nonexistent_key(self):
        """Test that extending a non-existent license raises ValueError."""
        license_key = "NONEXISTENT12345678901234"
        new_expires_at = datetime.utcnow() + timedelta(days=60)
        
        with patch('api_server.utils.license_service.db_pool.get_cursor') as mock_cursor:
            mock_ctx = MagicMock()
            mock_cursor.return_value.__enter__.return_value = mock_ctx
            
            with patch('api_server.utils.license_service.License.find_by_key', return_value=None):
                with pytest.raises(ValueError, match="License key not found"):
                    extend_license(license_key, new_expires_at)
    
    def test_extend_license_returns_correct_format(self):
        """Test that extend_license returns the correct response format."""
        license_key = "ABCD1234EFGH5678IJKL90MNO"
        new_expires_at = datetime(2025, 12, 31, 23, 59, 59)
        
        mock_license = MagicMock()
        mock_license.key = license_key
        
        with patch('api_server.utils.license_service.db_pool.get_cursor') as mock_cursor:
            mock_ctx = MagicMock()
            mock_cursor.return_value.__enter__.return_value = mock_ctx
            
            with patch('api_server.utils.license_service.License.find_by_key', return_value=mock_license):
                with patch('api_server.utils.license_service.License.update_expires_at'):
                    result = extend_license(license_key, new_expires_at)
                    
                    assert 'message' in result
                    assert 'expires_at' in result
                    assert result['expires_at'] == "2025-12-31T23:59:59"


class TestListLicenses:
    """Tests for license listing."""
    
    def test_list_licenses_without_filter(self):
        """Test listing all licenses without status filter."""
        mock_license1 = MagicMock()
        mock_license1.to_dict.return_value = {
            'id': 1,
            'key': 'LICENSE1234567890123456',
            'status': 'active',
            'expires_at': '2024-12-31T23:59:59',
            'max_sessions': 1,
            'created_at': '2024-01-01T00:00:00',
            'note': 'Test 1'
        }
        
        mock_license2 = MagicMock()
        mock_license2.to_dict.return_value = {
            'id': 2,
            'key': 'LICENSE2345678901234567',
            'status': 'expired',
            'expires_at': '2023-12-31T23:59:59',
            'max_sessions': 2,
            'created_at': '2023-01-01T00:00:00',
            'note': 'Test 2'
        }
        
        with patch('api_server.utils.license_service.db_pool.get_cursor') as mock_cursor:
            mock_ctx = MagicMock()
            mock_cursor.return_value.__enter__.return_value = mock_ctx
            mock_ctx.fetchone.return_value = {'count': 2}
            
            with patch('api_server.utils.license_service.License.list_all', return_value=[mock_license1, mock_license2]):
                result = list_licenses()
                
                assert len(result['licenses']) == 2
                assert result['total'] == 2
                assert result['limit'] == 100
                assert result['offset'] == 0
                # Verify id field is removed
                assert 'id' not in result['licenses'][0]
                assert 'id' not in result['licenses'][1]
    
    def test_list_licenses_with_status_filter(self):
        """Test listing licenses with status filter."""
        mock_license = MagicMock()
        mock_license.to_dict.return_value = {
            'id': 1,
            'key': 'ACTIVEKEY1234567890123456',
            'status': 'active',
            'expires_at': '2024-12-31T23:59:59',
            'max_sessions': 1,
            'created_at': '2024-01-01T00:00:00',
            'note': 'Active license'
        }
        
        with patch('api_server.utils.license_service.db_pool.get_cursor') as mock_cursor:
            mock_ctx = MagicMock()
            mock_cursor.return_value.__enter__.return_value = mock_ctx
            mock_ctx.fetchone.return_value = {'count': 1}
            
            with patch('api_server.utils.license_service.License.list_all', return_value=[mock_license]) as mock_list:
                result = list_licenses(status='active')
                
                # Verify License.list_all was called with status filter
                mock_list.assert_called_once_with(mock_ctx, 'active', 100, 0)
                assert len(result['licenses']) == 1
                assert result['licenses'][0]['status'] == 'active'
    
    def test_list_licenses_with_pagination(self):
        """Test listing licenses with pagination parameters."""
        with patch('api_server.utils.license_service.db_pool.get_cursor') as mock_cursor:
            mock_ctx = MagicMock()
            mock_cursor.return_value.__enter__.return_value = mock_ctx
            mock_ctx.fetchone.return_value = {'count': 150}
            
            with patch('api_server.utils.license_service.License.list_all', return_value=[]) as mock_list:
                result = list_licenses(limit=50, offset=50)
                
                # Verify pagination parameters were passed
                mock_list.assert_called_once_with(mock_ctx, None, 50, 50)
                assert result['limit'] == 50
                assert result['offset'] == 50
                assert result['total'] == 150
    
    def test_list_licenses_with_invalid_status(self):
        """Test that listing with invalid status raises ValueError."""
        with pytest.raises(ValueError, match="Invalid status"):
            list_licenses(status='invalid_status')
    
    def test_list_licenses_valid_statuses(self):
        """Test that all valid status values are accepted."""
        valid_statuses = ['active', 'expired', 'revoked']
        
        for status in valid_statuses:
            with patch('api_server.utils.license_service.db_pool.get_cursor') as mock_cursor:
                mock_ctx = MagicMock()
                mock_cursor.return_value.__enter__.return_value = mock_ctx
                mock_ctx.fetchone.return_value = {'count': 0}
                
                with patch('api_server.utils.license_service.License.list_all', return_value=[]):
                    # Should not raise ValueError
                    result = list_licenses(status=status)
                    assert result['licenses'] == []


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
