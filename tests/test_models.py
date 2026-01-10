"""
MIMIC - Model Tests
===================
Unit tests for database models.
"""

import pytest
from datetime import datetime, timezone, timedelta


class TestUserModel:
    """Tests for the User model."""
    
    def test_create_user(self, app, db_session):
        """Test creating a new user."""
        from models import User
        
        user = User(
            username='newuser',
            email='new@example.com',
            is_active=False,
            role='user'
        )
        user.set_password('SecurePassword123!')
        
        db_session.add(user)
        db_session.commit()
        
        assert user.id is not None
        assert user.username == 'newuser'
        assert user.email == 'new@example.com'
        assert user.is_active is False
        assert user.role == 'user'
    
    def test_password_hashing(self, app, db_session):
        """Test password hashing and verification."""
        from models import User
        
        user = User(username='passtest', email='pass@test.com')
        password = 'MySecurePassword123!'
        user.set_password(password)
        
        # Password should be hashed, not stored in plain text
        assert user.password_hash != password
        assert user.password_hash is not None
        
        # Password verification should work
        assert user.check_password(password) is True
        assert user.check_password('WrongPassword') is False
    
    def test_api_key_encryption(self, app, db_session):
        """Test API key encryption and decryption."""
        from models import User
        
        user = User(username='keytest', email='key@test.com')
        
        api_key = 'test_api_key_12345'
        api_secret = 'test_api_secret_67890'
        
        user.set_keys(api_key, api_secret)
        
        # Keys should be encrypted (different from original)
        assert user.api_key_enc != api_key
        assert user.api_secret_enc != api_secret
        
        # Decryption should return original values
        decrypted_key, decrypted_secret = user.get_keys()
        assert decrypted_key == api_key
        assert decrypted_secret == api_secret
    
    def test_referral_code_generation(self, app, db_session):
        """Test referral code generation."""
        from models import User
        
        code1 = User.generate_referral_code()
        code2 = User.generate_referral_code()
        
        # Codes should be unique
        assert code1 != code2
        
        # Codes should be 8 characters by default
        assert len(code1) == 8
        assert len(code2) == 8
        
        # Codes should only contain allowed characters
        allowed_chars = set('ABCDEFGHJKLMNPQRSTUVWXYZ23456789')
        assert set(code1).issubset(allowed_chars)
    
    def test_user_roles(self, app, db_session):
        """Test user role assignment."""
        from models import User
        
        regular_user = User(username='regular', email='regular@test.com', role='user')
        admin_user = User(username='admin', email='admin@test.com', role='admin')
        
        db_session.add_all([regular_user, admin_user])
        db_session.commit()
        
        assert regular_user.role == 'user'
        assert admin_user.role == 'admin'
    
    def test_subscription_defaults(self, app, db_session):
        """Test default subscription settings."""
        from models import User
        
        user = User(username='subtest', email='sub@test.com')
        db_session.add(user)
        db_session.commit()
        
        assert user.subscription_plan == 'free'
        assert user.subscription_expires_at is None
    
    def test_gamification_defaults(self, app, db_session):
        """Test default gamification settings."""
        from models import User
        
        user = User(username='gametest', email='game@test.com')
        db_session.add(user)
        db_session.commit()
        
        assert user.xp == 0
        assert user.total_trading_volume == 0.0
        assert user.discount_percent == 0.0


class TestTradeHistoryModel:
    """Tests for the TradeHistory model."""
    
    def test_create_trade(self, app, db_session, test_user):
        """Test creating a trade history record."""
        from models import TradeHistory
        
        trade = TradeHistory(
            user_id=test_user.id,
            symbol='BTCUSDT',
            side='BUY',
            entry_price=50000.0,
            amount=0.01,
            leverage=10
        )
        
        db_session.add(trade)
        db_session.commit()
        
        assert trade.id is not None
        assert trade.symbol == 'BTCUSDT'
        assert trade.side == 'BUY'
        assert trade.entry_price == 50000.0
    
    def test_trade_user_relationship(self, app, db_session, test_user):
        """Test trade-user relationship."""
        from models import TradeHistory
        
        trade = TradeHistory(
            user_id=test_user.id,
            symbol='ETHUSDT',
            side='SELL',
            entry_price=3000.0,
            amount=0.1
        )
        
        db_session.add(trade)
        db_session.commit()
        
        # Verify relationship
        assert trade.user_id == test_user.id


class TestBalanceHistoryModel:
    """Tests for the BalanceHistory model."""
    
    def test_create_balance_record(self, app, db_session, test_user):
        """Test creating a balance history record."""
        from models import BalanceHistory
        
        balance = BalanceHistory(
            user_id=test_user.id,
            balance=1000.0
        )
        
        db_session.add(balance)
        db_session.commit()
        
        assert balance.id is not None
        assert balance.balance == 1000.0
        assert balance.user_id == test_user.id


class TestMessageModel:
    """Tests for the Message model."""
    
    def test_create_message(self, app, db_session, test_user, test_admin):
        """Test creating a message."""
        from models import Message
        
        message = Message(
            sender_id=test_user.id,
            receiver_id=test_admin.id,
            subject='Test Subject',
            body='Test message body'
        )
        
        db_session.add(message)
        db_session.commit()
        
        assert message.id is not None
        assert message.subject == 'Test Subject'
        assert message.is_read is False


class TestApiKeyModel:
    """Tests for the ApiKey model."""
    
    def test_create_api_key(self, app, db_session, test_user):
        """Test creating an API key."""
        from models import ApiKey
        import secrets
        
        api_key = ApiKey(
            user_id=test_user.id,
            name='Test Key',
            key_hash='hashed_key_value',
            key_prefix='test123',
            permissions='read'
        )
        
        db_session.add(api_key)
        db_session.commit()
        
        assert api_key.id is not None
        assert api_key.name == 'Test Key'
        assert api_key.is_active is True
