"""
MIMIC Test Configuration
========================
Pytest fixtures and configuration for the test suite.
"""

import os
import sys
import pytest
import tempfile
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test environment before importing app
os.environ['FLASK_ENV'] = 'testing'
os.environ['TESTING'] = 'true'


@pytest.fixture(scope='session')
def app():
    """Create and configure a test Flask application instance."""
    # Create a temporary file for the test database
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    
    # Set test configuration
    os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'
    
    # Create a minimal test secret key for testing
    os.environ['FLASK_SECRET_KEY'] = 'test-secret-key-for-testing-only-32chars!'
    
    # Create a test master key (valid Fernet key)
    from cryptography.fernet import Fernet
    test_key = Fernet.generate_key().decode()
    os.environ['BRAIN_CAPITAL_MASTER_KEY'] = test_key
    
    # Now import the app
    from app import app as flask_app
    
    flask_app.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
        'SERVER_NAME': 'localhost',
    })
    
    # Create application context
    with flask_app.app_context():
        from models import db
        db.create_all()
        yield flask_app
        db.drop_all()
    
    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """Create a test client for the Flask application."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a CLI test runner for the Flask application."""
    return app.test_cli_runner()


@pytest.fixture
def db_session(app):
    """Create a database session for testing."""
    from models import db
    with app.app_context():
        connection = db.engine.connect()
        transaction = connection.begin()
        
        yield db.session
        
        transaction.rollback()
        connection.close()


@pytest.fixture
def test_user(app, db_session):
    """Create a test user for authentication tests."""
    from models import User
    
    user = User(
        username='testuser',
        email='test@example.com',
        is_active=True,
        role='user'
    )
    user.set_password('TestPassword123!')
    
    db_session.add(user)
    db_session.commit()
    
    yield user
    
    # Cleanup handled by db_session fixture


@pytest.fixture
def test_admin(app, db_session):
    """Create a test admin user for admin-specific tests."""
    from models import User
    
    admin = User(
        username='testadmin',
        email='admin@example.com',
        is_active=True,
        role='admin'
    )
    admin.set_password('AdminPassword123!')
    
    db_session.add(admin)
    db_session.commit()
    
    yield admin


@pytest.fixture
def authenticated_client(client, test_user):
    """Create an authenticated test client."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(test_user.id)
        sess['_fresh'] = True
    return client


@pytest.fixture
def admin_client(client, test_admin):
    """Create an authenticated admin test client."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(test_admin.id)
        sess['_fresh'] = True
    return client


# ==================== FastAPI Test Fixtures ====================

@pytest.fixture(scope='session')
def fastapi_app():
    """Create a test FastAPI application instance."""
    from app_fastapi import app as fa_app
    return fa_app


@pytest.fixture
def fastapi_client(fastapi_app):
    """Create a test client for FastAPI."""
    from fastapi.testclient import TestClient
    return TestClient(fastapi_app)


# ==================== Mock Fixtures ====================

@pytest.fixture
def mock_binance_client(mocker):
    """Mock the Binance client for trading tests."""
    mock_client = mocker.MagicMock()
    mock_client.futures_account_balance.return_value = [
        {'asset': 'USDT', 'balance': '1000.00', 'availableBalance': '950.00'}
    ]
    mock_client.futures_position_information.return_value = []
    mock_client.futures_create_order.return_value = {
        'orderId': 12345,
        'symbol': 'BTCUSDT',
        'status': 'NEW',
        'price': '50000.00',
        'executedQty': '0.01'
    }
    return mock_client


@pytest.fixture
def mock_redis(mocker):
    """Mock Redis for task queue tests."""
    mock = mocker.MagicMock()
    mock.get.return_value = None
    mock.set.return_value = True
    return mock


# ==================== Utility Fixtures ====================

@pytest.fixture
def sample_trade_data():
    """Sample trade data for testing."""
    return {
        'symbol': 'BTCUSDT',
        'side': 'BUY',
        'type': 'MARKET',
        'quantity': '0.01',
        'price': '50000.00',
        'leverage': 10
    }


@pytest.fixture
def sample_webhook_data():
    """Sample TradingView webhook data for testing."""
    return {
        'passphrase': 'test-passphrase',
        'ticker': 'BTCUSDT',
        'action': 'buy',
        'contracts': '0.01',
        'price': '50000.00'
    }
