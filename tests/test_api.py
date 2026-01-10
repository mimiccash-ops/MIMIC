"""
MIMIC - API Tests
=================
Integration tests for API endpoints.
"""

import pytest
import json


class TestHealthEndpoints:
    """Tests for health check endpoints."""
    
    def test_flask_health_check(self, client):
        """Test Flask app responds."""
        # Test that the app is running
        response = client.get('/')
        assert response.status_code in [200, 302]  # OK or redirect to login
    
    def test_fastapi_health_check(self, fastapi_client):
        """Test FastAPI health endpoint."""
        response = fastapi_client.get('/health')
        assert response.status_code == 200
        
        data = response.json()
        assert data['status'] == 'healthy'
    
    def test_fastapi_root_endpoint(self, fastapi_client):
        """Test FastAPI root endpoint."""
        response = fastapi_client.get('/')
        assert response.status_code == 200
        
        data = response.json()
        assert 'version' in data
        assert 'docs' in data


class TestAuthenticationEndpoints:
    """Tests for authentication endpoints."""
    
    def test_login_page_loads(self, client):
        """Test login page loads correctly."""
        response = client.get('/login')
        assert response.status_code == 200
        assert b'login' in response.data.lower() or b'Login' in response.data
    
    def test_register_page_loads(self, client):
        """Test registration page loads correctly."""
        response = client.get('/register')
        assert response.status_code == 200
    
    def test_login_with_invalid_credentials(self, client):
        """Test login fails with invalid credentials."""
        response = client.post('/login', data={
            'username': 'nonexistent',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        
        # Should not redirect to dashboard
        assert b'dashboard' not in response.data.lower() or response.status_code != 200
    
    def test_protected_route_requires_auth(self, client):
        """Test protected routes require authentication."""
        response = client.get('/dashboard')
        
        # Should redirect to login
        assert response.status_code in [302, 401, 403]
    
    def test_logout_endpoint(self, authenticated_client):
        """Test logout endpoint."""
        response = authenticated_client.get('/logout', follow_redirects=True)
        assert response.status_code == 200


class TestUserDashboard:
    """Tests for user dashboard."""
    
    def test_dashboard_accessible_when_authenticated(self, authenticated_client):
        """Test dashboard is accessible when authenticated."""
        response = authenticated_client.get('/dashboard')
        # Should be accessible or redirect to legal consent
        assert response.status_code in [200, 302]


class TestAdminEndpoints:
    """Tests for admin endpoints."""
    
    def test_admin_dashboard_requires_admin(self, authenticated_client):
        """Test admin dashboard requires admin role."""
        response = authenticated_client.get('/admin')
        # Regular user should not access admin
        assert response.status_code in [302, 403, 404]
    
    def test_admin_dashboard_accessible_to_admin(self, admin_client):
        """Test admin dashboard is accessible to admin."""
        response = admin_client.get('/admin')
        # Admin should access or be redirected somewhere valid
        assert response.status_code in [200, 302]


class TestAPIErrorHandling:
    """Tests for API error handling."""
    
    def test_404_error_handling(self, client):
        """Test 404 error is handled properly."""
        response = client.get('/nonexistent-route-12345')
        assert response.status_code == 404
    
    def test_fastapi_404_handling(self, fastapi_client):
        """Test FastAPI 404 error handling."""
        response = fastapi_client.get('/nonexistent-api-route')
        assert response.status_code == 404


class TestFastAPIEndpoints:
    """Tests for FastAPI specific endpoints."""
    
    def test_openapi_docs_available(self, fastapi_client):
        """Test OpenAPI docs are available."""
        response = fastapi_client.get('/docs')
        assert response.status_code == 200
    
    def test_redoc_available(self, fastapi_client):
        """Test ReDoc is available."""
        response = fastapi_client.get('/redoc')
        assert response.status_code == 200
    
    def test_openapi_json_available(self, fastapi_client):
        """Test OpenAPI JSON schema is available."""
        response = fastapi_client.get('/openapi.json')
        assert response.status_code == 200
        
        data = response.json()
        assert 'openapi' in data
        assert 'info' in data
        assert 'paths' in data


class TestSecurityMiddleware:
    """Tests for security middleware."""
    
    def test_security_headers_present(self, fastapi_client):
        """Test security headers are present in responses."""
        response = fastapi_client.get('/health')
        
        # Check for security headers
        assert 'x-content-type-options' in response.headers
        assert response.headers['x-content-type-options'] == 'nosniff'
        
        assert 'x-frame-options' in response.headers
        assert response.headers['x-frame-options'] == 'DENY'
    
    def test_request_id_header(self, fastapi_client):
        """Test request ID header is present."""
        response = fastapi_client.get('/health')
        
        assert 'x-request-id' in response.headers
        assert len(response.headers['x-request-id']) > 0


class TestCORSConfiguration:
    """Tests for CORS configuration."""
    
    def test_cors_headers_on_options(self, fastapi_client):
        """Test CORS headers on OPTIONS request."""
        response = fastapi_client.options(
            '/health',
            headers={'Origin': 'http://localhost:5000'}
        )
        
        # Should include CORS headers or handle the request
        assert response.status_code in [200, 204, 405]


class TestStaticFiles:
    """Tests for static file serving."""
    
    def test_static_css_accessible(self, client):
        """Test static CSS files are accessible."""
        response = client.get('/static/css/main.css')
        assert response.status_code == 200
    
    def test_static_js_accessible(self, client):
        """Test static JS files are accessible."""
        response = client.get('/static/js/main.js')
        assert response.status_code == 200
    
    def test_manifest_accessible(self, client):
        """Test PWA manifest is accessible."""
        response = client.get('/static/manifest.json')
        assert response.status_code == 200
