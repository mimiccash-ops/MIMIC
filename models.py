from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.fernet import Fernet
from config import Config
from datetime import datetime, timezone, timedelta
import secrets

db = SQLAlchemy()

# Налаштування шифрування
cipher_suite = None
if Config.MASTER_KEY_ENCRYPTION:
    try:
        cipher_suite = Fernet(Config.MASTER_KEY_ENCRYPTION)
    except Exception as e:
        print(f"⚠️ Encryption setup failed: {e}")

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)  # OPTIMIZED: Added index
    password_hash = db.Column(db.String(256))
    
    # Особисті дані
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)  # OPTIMIZED: Added index
    
    # Binance Keys (Stored as encrypted strings)
    api_key_enc = db.Column(db.String(500))
    api_secret_enc = db.Column(db.String(500))
    
    # Налаштування
    is_active = db.Column(db.Boolean, default=False, index=True)  # OPTIMIZED: Added index
    is_paused = db.Column(db.Boolean, default=False, index=True)  # OPTIMIZED: Added index
    role = db.Column(db.String(20), default='user', index=True)  # OPTIMIZED: Added index
    
    # Торгові параметри (Керуються адміном)
    custom_risk = db.Column(db.Float, default=0.0)
    custom_leverage = db.Column(db.Integer, default=0)
    max_positions = db.Column(db.Integer, default=5)
    risk_multiplier = db.Column(db.Float, default=1.0)  # Multiplier for position sizing (1.0 = normal)
    
    # DCA (Dollar Cost Averaging) settings
    dca_enabled = db.Column(db.Boolean, default=False)  # Enable DCA for this user
    dca_multiplier = db.Column(db.Float, default=1.0)  # Position size multiplier for DCA orders (1.0 = same size)
    dca_threshold = db.Column(db.Float, default=-2.0)  # Trigger DCA when PnL drops below this % (e.g., -2.0 = -2%)
    dca_max_orders = db.Column(db.Integer, default=3)  # Maximum number of DCA orders per position
    
    # Trailing Stop-Loss settings
    trailing_sl_enabled = db.Column(db.Boolean, default=False)  # Enable trailing stop-loss
    trailing_sl_activation = db.Column(db.Float, default=1.0)  # Activate trailing when profit reaches this %
    trailing_sl_callback = db.Column(db.Float, default=0.5)  # Trail distance in %
    
    # Risk Guardrails (Daily Equity Protection)
    daily_drawdown_limit_perc = db.Column(db.Float, default=10.0)  # Max daily drawdown % (e.g., 10 = -10%)
    daily_profit_target_perc = db.Column(db.Float, default=20.0)  # Daily profit lock % (e.g., 20 = +20%)
    risk_guardrails_enabled = db.Column(db.Boolean, default=False)  # Enable risk guardrails
    risk_guardrails_paused_at = db.Column(db.DateTime, nullable=True)  # When user was paused by guardrails
    risk_guardrails_reason = db.Column(db.String(100), nullable=True)  # Why paused (drawdown/profit_lock)
    
    # Referral System
    referral_code = db.Column(db.String(20), unique=True, nullable=True, index=True)  # User's unique referral code
    referred_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    referred_by = db.relationship('User', remote_side='User.id', backref=db.backref('referrals', lazy='dynamic'), foreign_keys=[referred_by_id])
    
    # Фінансова ціль
    target_balance = db.Column(db.Float, default=1000.0)
    
    # Telegram для сповіщень
    telegram_chat_id = db.Column(db.String(50))
    telegram_enabled = db.Column(db.Boolean, default=False)
    
    # Avatar - stores emoji or filename for custom image
    avatar = db.Column(db.String(100), default='🧑‍💻')  # Default emoji avatar
    avatar_type = db.Column(db.String(20), default='emoji')  # 'emoji' or 'image'
    
    # Subscription System
    subscription_plan = db.Column(db.String(50), default='free')  # 'free', 'basic', 'pro', 'enterprise'
    subscription_expires_at = db.Column(db.DateTime, nullable=True, index=True)  # NULL = no active subscription
    subscription_notified_expiring = db.Column(db.Boolean, default=False)  # Flag to avoid duplicate notifications
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)  # OPTIMIZED: Added index

    # Зв'язок з історією торгів та балансу - OPTIMIZED: Added lazy='dynamic' for large datasets
    trades = db.relationship('TradeHistory', backref='user', lazy='dynamic')
    balance_history = db.relationship('BalanceHistory', backref='user', lazy='dynamic')

    # OPTIMIZED: Add compound index for common query patterns
    __table_args__ = (
        db.Index('idx_user_active_role', 'is_active', 'role'),
        db.Index('idx_user_status', 'is_active', 'is_paused'),
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='scrypt')  # OPTIMIZED: Using scrypt (faster)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # Instance-level cache for decrypted keys
    _keys_cache = None
    
    def set_keys(self, api_key, api_secret):
        if cipher_suite:
            self.api_key_enc = cipher_suite.encrypt(api_key.encode()).decode()
            self.api_secret_enc = cipher_suite.encrypt(api_secret.encode()).decode()
        else:
            self.api_key_enc = api_key
            self.api_secret_enc = api_secret
        # Clear instance cache when keys are updated
        self._keys_cache = None

    def get_keys(self):
        """Get API keys with instance-level caching"""
        # Return cached value if available
        if self._keys_cache is not None:
            return self._keys_cache
        
        if not self.api_key_enc or not self.api_secret_enc:
            return None, None
        if cipher_suite:
            try:
                k = cipher_suite.decrypt(self.api_key_enc.encode()).decode()
                s = cipher_suite.decrypt(self.api_secret_enc.encode()).decode()
                self._keys_cache = (k, s)
                return self._keys_cache
            except (ValueError, TypeError) as e:
                # Log decryption errors for debugging
                print(f"⚠️ Key decryption failed for user {self.id}: {e}")
                return None, None
        self._keys_cache = (self.api_key_enc, self.api_secret_enc)
        return self._keys_cache

    @staticmethod
    def generate_referral_code(length=8):
        """Generate a unique referral code"""
        chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'  # Excluding confusing chars: I, O, 0, 1
        while True:
            code = ''.join(secrets.choice(chars) for _ in range(length))
            # Check if code already exists
            if not User.query.filter_by(referral_code=code).first():
                return code

    def ensure_referral_code(self):
        """Ensure the user has a referral code, generate one if missing"""
        if not self.referral_code:
            self.referral_code = self.generate_referral_code()
            return True
        return False

    def get_referral_stats(self):
        """Get referral statistics for this user"""
        from sqlalchemy import func
        
        referral_count = self.referrals.count()
        total_commission = db.session.query(func.coalesce(func.sum(ReferralCommission.amount), 0.0))\
            .filter(ReferralCommission.referrer_id == self.id).scalar()
        pending_commission = db.session.query(func.coalesce(func.sum(ReferralCommission.amount), 0.0))\
            .filter(ReferralCommission.referrer_id == self.id, ReferralCommission.is_paid == False).scalar()
        
        return {
            'referral_count': referral_count,
            'total_commission': float(total_commission or 0),
            'pending_commission': float(pending_commission or 0),
            'paid_commission': float((total_commission or 0) - (pending_commission or 0))
        }

    # ==================== SUBSCRIPTION HELPERS ====================
    
    def has_active_subscription(self) -> bool:
        """Check if user has an active (non-expired) subscription"""
        if not self.subscription_expires_at:
            return False
        now = datetime.now(timezone.utc)
        expires = self.subscription_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return now < expires
    
    def subscription_days_remaining(self) -> int:
        """Get number of days remaining in subscription"""
        if not self.subscription_expires_at:
            return 0
        now = datetime.now(timezone.utc)
        expires = self.subscription_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if now >= expires:
            return 0
        return (expires - now).days
    
    def extend_subscription(self, days: int = 30, plan: str = None):
        """Extend subscription by specified days"""
        now = datetime.now(timezone.utc)
        
        # If currently has active subscription, extend from expiry date
        if self.subscription_expires_at:
            expires = self.subscription_expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires > now:
                base_date = expires
            else:
                base_date = now
        else:
            base_date = now
        
        self.subscription_expires_at = base_date + timedelta(days=days)
        if plan:
            self.subscription_plan = plan
        self.subscription_notified_expiring = False  # Reset notification flag
        
        # Auto-activate user when subscription is purchased
        if not self.is_active:
            self.is_active = True
    
    def deactivate_expired_subscription(self):
        """Deactivate user if subscription has expired"""
        if not self.has_active_subscription():
            self.is_active = False
            return True
        return False

class Payment(db.Model):
    """Crypto payment transactions for subscription purchases"""
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Payment provider details (Plisio)
    provider = db.Column(db.String(50), default='plisio')  # 'plisio', 'manual', etc.
    provider_txn_id = db.Column(db.String(200), unique=True, nullable=True, index=True)  # Plisio txn_id
    
    # Payment amounts
    amount_usd = db.Column(db.Float, nullable=False)  # Amount in USD
    amount_crypto = db.Column(db.Float, nullable=True)  # Amount in crypto
    currency = db.Column(db.String(20), default='USDT_TRC20')  # Crypto currency
    
    # Subscription details
    plan = db.Column(db.String(50), nullable=False)  # 'basic', 'pro', 'enterprise'
    days = db.Column(db.Integer, default=30)  # Subscription days purchased
    
    # Status tracking
    status = db.Column(db.String(30), default='pending', index=True)  # pending, completed, expired, cancelled, error
    
    # Wallet info
    wallet_address = db.Column(db.String(200), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)  # Invoice expiration
    
    # Relationships
    user = db.relationship('User', backref=db.backref('payments', lazy='dynamic'))
    
    # Indexes
    __table_args__ = (
        db.Index('idx_payment_user_status', 'user_id', 'status'),
        db.Index('idx_payment_provider_txn', 'provider', 'provider_txn_id'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'provider': self.provider,
            'provider_txn_id': self.provider_txn_id,
            'amount_usd': self.amount_usd,
            'amount_crypto': self.amount_crypto,
            'currency': self.currency,
            'plan': self.plan,
            'days': self.days,
            'status': self.status,
            'wallet_address': self.wallet_address,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
        }


class TradeHistory(db.Model):
    __tablename__ = 'trade_history'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)  # OPTIMIZED: Added index + cascade
    symbol = db.Column(db.String(20), index=True)  # OPTIMIZED: Added index
    side = db.Column(db.String(10))
    pnl = db.Column(db.Float)
    roi = db.Column(db.Float)
    close_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)  # OPTIMIZED: Added index
    node_name = db.Column(db.String(50))

    # OPTIMIZED: Compound indexes for common queries
    __table_args__ = (
        db.Index('idx_trade_user_time', 'user_id', 'close_time'),
        db.Index('idx_trade_symbol_time', 'symbol', 'close_time'),
    )

    def to_dict(self):
        return {
            'time': self.close_time.strftime("%H:%M:%S %d/%m"),
            'symbol': self.symbol,
            'side': self.side,
            'pnl': round(self.pnl, 2),
            'roi': round(self.roi, 2),
            'node': self.node_name
        }


class ReferralCommission(db.Model):
    """Track commissions earned from referred users"""
    __tablename__ = 'referral_commissions'
    
    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    referred_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    trade_id = db.Column(db.Integer, db.ForeignKey('trade_history.id', ondelete='SET NULL'), nullable=True, index=True)
    
    commission_type = db.Column(db.String(20), nullable=False)  # 'profit' or 'fee'
    source_amount = db.Column(db.Float, default=0.0)  # Original profit/fee amount
    commission_rate = db.Column(db.Float, default=0.05)  # Commission rate (default 5%)
    amount = db.Column(db.Float, default=0.0)  # Commission amount earned
    
    is_paid = db.Column(db.Boolean, default=False, index=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    # Relationships
    referrer = db.relationship('User', foreign_keys=[referrer_id], backref=db.backref('commissions_earned', lazy='dynamic'))
    referred_user = db.relationship('User', foreign_keys=[referred_user_id], backref=db.backref('commissions_generated', lazy='dynamic'))
    trade = db.relationship('TradeHistory', backref='referral_commission')
    
    # OPTIMIZED: Compound indexes for commission queries
    __table_args__ = (
        db.Index('idx_commission_referrer_paid', 'referrer_id', 'is_paid'),
        db.Index('idx_commission_referrer_time', 'referrer_id', 'created_at'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'referred_username': self.referred_user.username if self.referred_user else 'Unknown',
            'type': self.commission_type,
            'source_amount': round(self.source_amount, 2),
            'rate': f"{self.commission_rate * 100:.1f}%",
            'amount': round(self.amount, 2),
            'is_paid': self.is_paid,
            'created_at': self.created_at.strftime("%d.%m.%Y %H:%M") if self.created_at else None
        }
    
    @classmethod
    def create_from_profit(cls, referred_user_id: int, trade_id: int, profit: float, commission_rate: float = 0.05):
        """Create a commission record from a profitable trade"""
        user = User.query.get(referred_user_id)
        if not user or not user.referred_by_id or profit <= 0:
            return None
        
        commission_amount = profit * commission_rate
        
        commission = cls(
            referrer_id=user.referred_by_id,
            referred_user_id=referred_user_id,
            trade_id=trade_id,
            commission_type='profit',
            source_amount=profit,
            commission_rate=commission_rate,
            amount=commission_amount
        )
        db.session.add(commission)
        return commission

class BalanceHistory(db.Model):
    __tablename__ = 'balance_history'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)  # OPTIMIZED: Added index + cascade
    balance = db.Column(db.Float, default=0.0)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)  # OPTIMIZED: Added index

    # OPTIMIZED: Compound index for time-series queries
    __table_args__ = (
        db.Index('idx_balance_user_time', 'user_id', 'timestamp'),
    )


class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)  # OPTIMIZED: Added index
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)  # OPTIMIZED: Added index
    subject = db.Column(db.String(200), default='')
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, index=True)  # OPTIMIZED: Added index
    is_from_admin = db.Column(db.Boolean, default=False, index=True)  # OPTIMIZED: Added index
    parent_id = db.Column(db.Integer, db.ForeignKey('messages.id', ondelete='CASCADE'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)  # OPTIMIZED: Added index
    
    # OPTIMIZED: Use joined loading for frequently accessed relationships
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages', lazy='joined')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_messages', lazy='joined')
    replies = db.relationship('Message', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')
    
    # OPTIMIZED: Compound indexes for message queries
    __table_args__ = (
        db.Index('idx_message_recipient_read', 'recipient_id', 'is_read'),
        db.Index('idx_message_sender_time', 'sender_id', 'created_at'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'sender_name': f"{self.sender.first_name or ''} {self.sender.last_name or ''}".strip() or self.sender.username,
            'recipient_id': self.recipient_id,
            'subject': self.subject,
            'content': self.content,
            'is_read': self.is_read,
            'is_from_admin': self.is_from_admin,
            'parent_id': self.parent_id,
            'created_at': self.created_at.strftime("%d.%m.%Y %H:%M"),
            'replies_count': self.replies.count()
        }


class PasswordResetToken(db.Model):
    """Токен для відновлення паролю через Email або Telegram"""
    __tablename__ = 'password_reset_tokens'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)  # OPTIMIZED: Added index
    token = db.Column(db.String(100), unique=True, nullable=False, index=True)  # OPTIMIZED: Added index
    code = db.Column(db.String(6), nullable=False)
    method = db.Column(db.String(20), nullable=False)
    is_used = db.Column(db.Boolean, default=False, index=True)  # OPTIMIZED: Added index
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False, index=True)  # OPTIMIZED: Added index
    
    user = db.relationship('User', backref='reset_tokens')
    
    # OPTIMIZED: Compound indexes for token validation
    __table_args__ = (
        db.Index('idx_token_user_used', 'user_id', 'is_used'),
        db.Index('idx_token_expires', 'expires_at', 'is_used'),
    )
    
    @staticmethod
    def generate_token():
        """Генерація безпечного токену"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def generate_code():
        """Генерація 6-значного коду"""
        return ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    
    @classmethod
    def create_for_user(cls, user_id, method='email', expires_minutes=15):
        """Створення нового токену для користувача"""
        # OPTIMIZED: Use bulk delete for better performance
        cls.query.filter_by(user_id=user_id, is_used=False).delete()
        
        token = cls(
            user_id=user_id,
            token=cls.generate_token(),
            code=cls.generate_code(),
            method=method,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
        )
        db.session.add(token)
        db.session.commit()
        return token
    
    def is_valid(self):
        """Перевірка чи токен ще дійсний"""
        if self.is_used:
            return False
        # Handle both timezone-aware and naive datetimes from database
        now = datetime.now(timezone.utc)
        expires = self.expires_at
        if expires.tzinfo is None:
            # If expires_at is naive (from SQLite), assume it's UTC
            expires = expires.replace(tzinfo=timezone.utc)
        if now > expires:
            return False
        return True
    
    def mark_used(self):
        """Позначити токен як використаний"""
        self.is_used = True
        db.session.commit()


class ExchangeConfig(db.Model):
    """Admin-controlled exchange availability configuration with admin's own API keys for verification"""
    __tablename__ = 'exchange_configs'
    
    id = db.Column(db.Integer, primary_key=True)
    exchange_name = db.Column(db.String(50), unique=True, nullable=False, index=True)  # OPTIMIZED: Added index
    display_name = db.Column(db.String(100), nullable=False)
    is_enabled = db.Column(db.Boolean, default=False, index=True)  # OPTIMIZED: Added index
    requires_passphrase = db.Column(db.Boolean, default=False)
    description = db.Column(db.Text, nullable=True)
    
    # Admin's API keys for exchange verification (encrypted)
    admin_api_key = db.Column(db.String(500), nullable=True)  # Encrypted
    admin_api_secret = db.Column(db.String(500), nullable=True)  # Encrypted
    admin_passphrase = db.Column(db.String(500), nullable=True)  # Encrypted (for OKX/KuCoin)
    is_verified = db.Column(db.Boolean, default=False, index=True)  # OPTIMIZED: Added index
    verified_at = db.Column(db.DateTime, nullable=True)
    verification_error = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # OPTIMIZED: Compound index for enabled/verified queries
    __table_args__ = (
        db.Index('idx_exchange_enabled_verified', 'is_enabled', 'is_verified'),
    )
    
    def set_admin_api_secret(self, plain_secret: str):
        """Encrypt and store admin API secret"""
        if not plain_secret:
            self.admin_api_secret = None
            return
        if cipher_suite:
            self.admin_api_secret = cipher_suite.encrypt(plain_secret.encode()).decode()
        else:
            self.admin_api_secret = plain_secret
    
    def get_admin_api_secret(self) -> str:
        """Decrypt and return admin API secret"""
        if not self.admin_api_secret:
            return None
        if cipher_suite:
            try:
                return cipher_suite.decrypt(self.admin_api_secret.encode()).decode()
            except (ValueError, TypeError):
                return None
        return self.admin_api_secret
    
    def set_admin_passphrase(self, plain_passphrase: str):
        """Encrypt and store admin passphrase"""
        if not plain_passphrase:
            self.admin_passphrase = None
            return
        if cipher_suite:
            self.admin_passphrase = cipher_suite.encrypt(plain_passphrase.encode()).decode()
        else:
            self.admin_passphrase = plain_passphrase
    
    def get_admin_passphrase(self) -> str:
        """Decrypt and return admin passphrase"""
        if not self.admin_passphrase:
            return None
        if cipher_suite:
            try:
                return cipher_suite.decrypt(self.admin_passphrase.encode()).decode()
            except (ValueError, TypeError):
                return None
        return self.admin_passphrase
    
    def to_dict(self, include_admin_keys: bool = False):
        data = {
            'id': self.id,
            'exchange_name': self.exchange_name,
            'display_name': self.display_name,
            'is_enabled': self.is_enabled,
            'is_verified': self.is_verified,
            'requires_passphrase': self.requires_passphrase,
            'description': self.description,
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
            'verification_error': self.verification_error
        }
        if include_admin_keys:
            data['admin_api_key'] = self.admin_api_key[:8] + '...' if self.admin_api_key and len(self.admin_api_key) > 8 else '***'
            data['has_admin_keys'] = bool(self.admin_api_key and self.admin_api_secret)
        return data


class UserExchange(db.Model):
    """User's Exchange API Keys - connects to admin-enabled exchanges"""
    __tablename__ = 'user_exchanges'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)  # OPTIMIZED: Added index + cascade
    exchange_name = db.Column(db.String(50), nullable=False, index=True)  # OPTIMIZED: Added index
    label = db.Column(db.String(100), nullable=False)
    api_key = db.Column(db.String(500), nullable=False)
    api_secret = db.Column(db.String(500), nullable=False)
    passphrase = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(20), default='PENDING', index=True)  # OPTIMIZED: Added index
    is_active = db.Column(db.Boolean, default=False, index=True)  # OPTIMIZED: Added index
    trading_enabled = db.Column(db.Boolean, default=False, index=True)  # OPTIMIZED: Added index
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    user = db.relationship('User', backref='exchanges')
    
    # OPTIMIZED: Compound indexes for user exchange queries
    __table_args__ = (
        db.Index('idx_user_exchange_status', 'user_id', 'status'),
        db.Index('idx_user_exchange_active', 'user_id', 'is_active', 'trading_enabled'),
    )
    
    def set_api_secret(self, plain_secret: str):
        """Encrypt and store API secret"""
        if cipher_suite:
            self.api_secret = cipher_suite.encrypt(plain_secret.encode()).decode()
        else:
            self.api_secret = plain_secret
    
    def get_api_secret(self) -> str:
        """Decrypt and return API secret"""
        if not self.api_secret:
            return None
        if cipher_suite:
            try:
                return cipher_suite.decrypt(self.api_secret.encode()).decode()
            except (ValueError, TypeError):
                return None
        return self.api_secret
    
    def set_passphrase(self, plain_passphrase: str):
        """Encrypt and store passphrase"""
        if not plain_passphrase:
            self.passphrase = None
            return
        if cipher_suite:
            self.passphrase = cipher_suite.encrypt(plain_passphrase.encode()).decode()
        else:
            self.passphrase = plain_passphrase
    
    def get_passphrase(self) -> str:
        """Decrypt and return passphrase"""
        if not self.passphrase:
            return None
        if cipher_suite:
            try:
                return cipher_suite.decrypt(self.passphrase.encode()).decode()
            except (ValueError, TypeError):
                return None
        return self.passphrase
    
    def to_dict(self, include_secrets: bool = False):
        """Convert to dictionary, optionally including secrets"""
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'exchange_name': self.exchange_name,
            'label': self.label,
            'api_key': self.api_key if include_secrets else '***',
            'status': self.status,
            'is_active': self.is_active,
            'trading_enabled': self.trading_enabled,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        if include_secrets:
            data['api_secret'] = self.get_api_secret()
            data['passphrase'] = self.get_passphrase()
        return data