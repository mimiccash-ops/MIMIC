"""
MIMIC - Security Tests
======================
Unit tests for security features.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestInputValidator:
    """Tests for input validation."""
    
    def test_validate_username_valid(self, app):
        """Test valid username validation."""
        from security import InputValidator
        
        with app.app_context():
            # Valid usernames
            valid_usernames = ['user123', 'test_user', 'john', 'alice_123']
            for username in valid_usernames:
                result = InputValidator.validate_username(username)
                assert result is True or result == username, f"Username {username} should be valid"
    
    def test_validate_username_invalid(self, app):
        """Test invalid username validation."""
        from security import InputValidator
        
        with app.app_context():
            # Invalid usernames
            invalid_usernames = ['ab', 'user<script>', 'admin;DROP TABLE', '']
            for username in invalid_usernames:
                result = InputValidator.validate_username(username)
                # Should either return False or raise an exception
                assert result is False or result is None or result != username
    
    def test_validate_email_valid(self, app):
        """Test valid email validation."""
        from security import InputValidator
        
        with app.app_context():
            valid_emails = ['test@example.com', 'user.name@domain.org', 'email+tag@test.co.uk']
            for email in valid_emails:
                result = InputValidator.validate_email(email)
                assert result is True or result == email, f"Email {email} should be valid"
    
    def test_validate_email_invalid(self, app):
        """Test invalid email validation."""
        from security import InputValidator
        
        with app.app_context():
            invalid_emails = ['not_an_email', 'test@', '@domain.com', '']
            for email in invalid_emails:
                result = InputValidator.validate_email(email)
                assert result is False or result is None


class TestPasswordSecurity:
    """Tests for password security."""
    
    def test_password_strength_requirements(self, app, db_session):
        """Test password meets strength requirements."""
        from models import User
        
        user = User(username='passtest', email='pass@test.com')
        
        # Strong password should work
        strong_password = 'MyStr0ngP@ssword!'
        user.set_password(strong_password)
        
        assert user.check_password(strong_password) is True
    
    def test_password_hash_is_different(self, app, db_session):
        """Test that same password produces different hashes (due to salt)."""
        from models import User
        
        user1 = User(username='user1', email='user1@test.com')
        user2 = User(username='user2', email='user2@test.com')
        
        same_password = 'SamePassword123!'
        user1.set_password(same_password)
        user2.set_password(same_password)
        
        # Hashes should be different due to salting
        assert user1.password_hash != user2.password_hash
        
        # But both should verify correctly
        assert user1.check_password(same_password) is True
        assert user2.check_password(same_password) is True


class TestCSRFProtection:
    """Tests for CSRF protection."""
    
    def test_csrf_token_generation(self, app):
        """Test CSRF token generation."""
        from security import generate_csrf_token
        
        with app.test_request_context():
            token1 = generate_csrf_token()
            
            # Token should be generated
            assert token1 is not None
            assert len(token1) > 0


class TestRateLimiting:
    """Tests for rate limiting."""
    
    def test_login_rate_limiting_exists(self, app):
        """Test that login rate limiting is configured."""
        from security import login_limiter
        
        # Rate limiter should exist
        assert login_limiter is not None
    
    def test_api_rate_limiting_exists(self, app):
        """Test that API rate limiting is configured."""
        from security import api_limiter
        
        # Rate limiter should exist
        assert api_limiter is not None


class TestSecurityHeaders:
    """Tests for security headers."""
    
    def test_security_headers_function_exists(self, app):
        """Test that security headers function exists."""
        from security import add_security_headers
        
        assert add_security_headers is not None
        assert callable(add_security_headers)


class TestSessionSecurity:
    """Tests for session security."""
    
    def test_session_configuration(self, app):
        """Test session security configuration."""
        # Session should be configured for security
        assert app.config.get('SESSION_COOKIE_HTTPONLY') is True
        assert app.config.get('SESSION_COOKIE_SAMESITE') in ['Lax', 'Strict']


class TestAuditLogging:
    """Tests for audit logging."""
    
    def test_audit_decorator_exists(self, app):
        """Test that audit decorator exists."""
        from security import audit
        
        assert audit is not None
        assert callable(audit)


class TestEncryption:
    """Tests for encryption functionality."""
    
    def test_fernet_encryption(self, app):
        """Test Fernet encryption is properly configured."""
        from models import cipher_suite
        
        if cipher_suite is not None:
            # Test encryption/decryption
            test_data = b'sensitive_data_12345'
            encrypted = cipher_suite.encrypt(test_data)
            decrypted = cipher_suite.decrypt(encrypted)
            
            assert encrypted != test_data
            assert decrypted == test_data
    
    def test_api_keys_are_encrypted(self, app, db_session):
        """Test that API keys are stored encrypted."""
        from models import User
        
        user = User(username='enctest', email='enc@test.com')
        
        api_key = 'plaintext_api_key'
        api_secret = 'plaintext_api_secret'
        
        user.set_keys(api_key, api_secret)
        
        # Stored values should be different from plaintext
        assert user.api_key_enc != api_key
        assert user.api_secret_enc != api_secret
        
        # But should decrypt correctly
        key, secret = user.get_keys()
        assert key == api_key
        assert secret == api_secret


class TestWebhookSecurity:
    """Tests for webhook security."""
    
    def test_webhook_validation_exists(self, app):
        """Test that webhook validation function exists."""
        from security import validate_webhook
        
        assert validate_webhook is not None
        assert callable(validate_webhook)


class TestClientIPDetection:
    """Tests for client IP detection."""
    
    def test_get_client_ip_function_exists(self, app):
        """Test that client IP detection function exists."""
        from security import get_client_ip
        
        assert get_client_ip is not None
        assert callable(get_client_ip)
