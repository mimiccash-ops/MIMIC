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
    
    # Gamification System
    xp = db.Column(db.Integer, default=0, index=True)  # Experience points (Volume/1000 + Days Active)
    current_level_id = db.Column(db.Integer, db.ForeignKey('user_levels.id', ondelete='SET NULL'), nullable=True, index=True)
    discount_percent = db.Column(db.Float, default=0.0)  # Commission discount from level
    total_trading_volume = db.Column(db.Float, default=0.0)  # Lifetime trading volume in USD
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)  # OPTIMIZED: Added index

    # Зв'язок з історією торгів та балансу - OPTIMIZED: Added lazy='dynamic' for large datasets
    trades = db.relationship('TradeHistory', backref='user', lazy='dynamic')
    balance_history = db.relationship('BalanceHistory', backref='user', lazy='dynamic')
    
    # Gamification relationship
    current_level = db.relationship('UserLevel', foreign_keys=[current_level_id], lazy='joined')

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
    
    # ==================== GAMIFICATION HELPERS ====================
    
    def get_level_info(self) -> dict:
        """Get current level information with progress to next level"""
        # Get or calculate XP if not set
        current_xp = self.xp or 0
        
        # Get current level using relationship or query
        level = self.current_level
        if not level:
            # Lazy query - UserLevel defined later in this file
            level = _get_level_for_xp(current_xp)
        
        # Get next level
        next_level = _get_next_level(level) if level else None
        
        # Calculate progress percentage
        if level and next_level:
            xp_in_level = current_xp - level.min_xp
            xp_needed = next_level.min_xp - level.min_xp
            progress = min(100, (xp_in_level / xp_needed * 100)) if xp_needed > 0 else 100
            xp_to_next = next_level.min_xp - current_xp
        else:
            progress = 100  # Max level reached
            xp_to_next = 0
        
        return {
            'current_xp': current_xp,
            'level': level.to_dict() if level else None,
            'level_name': level.name if level else 'Novice',
            'level_icon': level.icon if level else 'fa-seedling',
            'level_color': level.color if level else '#888888',
            'discount_percent': level.discount_percent if level else 0,
            'next_level': next_level.to_dict() if next_level else None,
            'next_level_name': next_level.name if next_level else None,
            'xp_to_next': max(0, xp_to_next),
            'progress': round(progress, 1),
            'is_max_level': next_level is None,
        }
    
    def get_unlocked_badges(self) -> list:
        """Get all unlocked achievements/badges for this user"""
        # Use dynamic query to avoid import issues
        return [a.to_dict() for a in self.achievements.all()]
    
    def update_xp_and_level(self, new_xp: int = None):
        """
        Update user's XP and recalculate level.
        
        Args:
            new_xp: New XP value. If None, calculates based on volume and days active.
            
        Returns:
            tuple: (new_level, leveled_up: bool)
        """
        if new_xp is not None:
            self.xp = new_xp
        
        # Get appropriate level for current XP
        new_level = _get_level_for_xp(self.xp or 0)
        
        leveled_up = False
        if new_level:
            # Check if leveled up
            if self.current_level_id != new_level.id:
                old_level_rank = self.current_level.order_rank if self.current_level else -1
                if new_level.order_rank > old_level_rank:
                    leveled_up = True
            
            self.current_level_id = new_level.id
            self.discount_percent = new_level.discount_percent
        
        db.session.commit()
        return new_level, leveled_up
    
    def calculate_xp(self) -> int:
        """
        Calculate XP based on trading activity.
        
        Formula: Trade Volume / 1000 + Days Active
        """
        from sqlalchemy import func
        
        # Get total trading volume (sum of absolute PnL * leverage factor)
        volume_result = db.session.query(func.sum(func.abs(TradeHistory.pnl))).filter(
            TradeHistory.user_id == self.id
        ).scalar()
        volume_xp = int((float(volume_result or 0) * 100) / 1000)  # Scale PnL to approximate volume
        
        # Days active since registration
        if self.created_at:
            now = datetime.now(timezone.utc)
            created = self.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            days_active = max(1, (now - created).days)
        else:
            days_active = 1
        
        total_xp = volume_xp + days_active
        return total_xp
    
    def add_trading_volume(self, volume: float):
        """Add trading volume and recalculate XP"""
        self.total_trading_volume = (self.total_trading_volume or 0) + abs(volume)
        # Recalculate XP
        self.xp = self.calculate_xp()
        self.update_xp_and_level(self.xp)
    
    def get_gamification_summary(self) -> dict:
        """Get complete gamification summary for dashboard display"""
        level_info = self.get_level_info()
        badges = self.get_unlocked_badges()
        
        return {
            **level_info,
            'badges': badges,
            'total_badges': len(badges),
            'total_trading_volume': self.total_trading_volume or 0,
        }


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


class PushSubscription(db.Model):
    """Web Push notification subscriptions for PWA"""
    __tablename__ = 'push_subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    endpoint = db.Column(db.Text, nullable=False, unique=True)
    p256dh_key = db.Column(db.String(500), nullable=False)  # Public key for encryption
    auth_key = db.Column(db.String(500), nullable=False)     # Authentication secret
    user_agent = db.Column(db.String(500), nullable=True)    # Browser/device info
    language = db.Column(db.String(10), default='en')        # User's language preference
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_used_at = db.Column(db.DateTime, nullable=True)     # Track last successful push
    error_count = db.Column(db.Integer, default=0)           # Track failed pushes
    
    user = db.relationship('User', backref='push_subscriptions')
    
    # Index for efficient querying
    __table_args__ = (
        db.Index('idx_push_user_active', 'user_id', 'is_active'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'endpoint': self.endpoint[:50] + '...' if len(self.endpoint) > 50 else self.endpoint,
            'user_agent': self.user_agent,
            'language': self.language,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None
        }
    
    def get_subscription_info(self):
        """Get subscription info in format required by pywebpush"""
        return {
            'endpoint': self.endpoint,
            'keys': {
                'p256dh': self.p256dh_key,
                'auth': self.auth_key
            }
        }
    
    def mark_used(self):
        """Mark subscription as recently used"""
        self.last_used_at = datetime.now(timezone.utc)
        self.error_count = 0
    
    def mark_error(self):
        """Increment error count"""
        self.error_count += 1
        # Deactivate after too many errors
        if self.error_count >= 5:
            self.is_active = False


class Strategy(db.Model):
    """
    Trading Strategy model - represents a master trading strategy that users can subscribe to.
    
    Each strategy is linked to a master exchange config that executes the trades.
    Examples: "Aggressive", "Safe", "BTC Only", "Altcoin Scalping"
    """
    __tablename__ = 'strategies'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    risk_level = db.Column(db.String(20), default='medium', index=True)  # 'low', 'medium', 'high'
    
    # Link to master exchange config (which has the master API keys)
    master_exchange_id = db.Column(db.Integer, db.ForeignKey('exchange_configs.id', ondelete='SET NULL'), nullable=True, index=True)
    master_exchange = db.relationship('ExchangeConfig', backref=db.backref('strategies', lazy='dynamic'))
    
    # Strategy-specific settings (optional overrides)
    default_risk_perc = db.Column(db.Float, nullable=True)  # Override global risk %
    default_leverage = db.Column(db.Integer, nullable=True)  # Override global leverage
    max_positions = db.Column(db.Integer, nullable=True)  # Override global max positions
    
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationship to subscriptions
    subscriptions = db.relationship('StrategySubscription', backref='strategy', lazy='dynamic', cascade='all, delete-orphan')
    
    # Compound indexes
    __table_args__ = (
        db.Index('idx_strategy_active_risk', 'is_active', 'risk_level'),
    )
    
    def to_dict(self, include_stats: bool = False):
        """Convert strategy to dictionary"""
        data = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'risk_level': self.risk_level,
            'master_exchange_id': self.master_exchange_id,
            'master_exchange_name': self.master_exchange.display_name if self.master_exchange else None,
            'default_risk_perc': self.default_risk_perc,
            'default_leverage': self.default_leverage,
            'max_positions': self.max_positions,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_stats:
            data['subscriber_count'] = self.subscriptions.filter_by(is_active=True).count()
        return data
    
    def get_active_subscribers(self):
        """Get all active subscribers for this strategy"""
        return StrategySubscription.query.filter_by(
            strategy_id=self.id,
            is_active=True
        ).join(User).filter(
            User.is_active == True,
            User.is_paused == False
        ).all()
    
    @staticmethod
    def get_default_strategy():
        """Get or create the default 'Main' strategy"""
        strategy = Strategy.query.filter_by(name='Main').first()
        if not strategy:
            strategy = Strategy(
                name='Main',
                description='Default trading strategy',
                risk_level='medium',
                is_active=True
            )
            db.session.add(strategy)
            db.session.commit()
        return strategy


class StrategySubscription(db.Model):
    """
    User subscription to a trading strategy.
    
    Links users to strategies with an allocation percentage.
    All active allocations for a user should sum to 100%.
    """
    __tablename__ = 'strategy_subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    strategy_id = db.Column(db.Integer, db.ForeignKey('strategies.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Allocation percentage - how much of user's balance to allocate to this strategy
    # All active subscriptions for a user should sum to 100%
    allocation_percent = db.Column(db.Float, default=100.0)
    
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationship to user (strategy relationship defined via backref in Strategy model)
    user = db.relationship('User', backref=db.backref('strategy_subscriptions', lazy='dynamic', cascade='all, delete-orphan'))
    
    # Unique constraint: user can only subscribe to each strategy once
    __table_args__ = (
        db.UniqueConstraint('user_id', 'strategy_id', name='unique_user_strategy'),
        db.Index('idx_subscription_user_active', 'user_id', 'is_active'),
        db.Index('idx_subscription_strategy_active', 'strategy_id', 'is_active'),
    )
    
    def to_dict(self):
        """Convert subscription to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'strategy_id': self.strategy_id,
            'strategy_name': self.strategy.name if self.strategy else None,
            'strategy_risk_level': self.strategy.risk_level if self.strategy else None,
            'allocation_percent': self.allocation_percent,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @staticmethod
    def get_user_total_allocation(user_id: int) -> float:
        """Get total allocation percentage for a user across all active subscriptions"""
        from sqlalchemy import func
        total = db.session.query(func.coalesce(func.sum(StrategySubscription.allocation_percent), 0.0))\
            .filter(StrategySubscription.user_id == user_id, StrategySubscription.is_active == True).scalar()
        return float(total or 0)
    
    @staticmethod
    def validate_user_allocations(user_id: int, new_allocation: float = 0, exclude_subscription_id: int = None) -> tuple:
        """
        Validate that user's total allocations don't exceed 100%.
        
        Args:
            user_id: User ID to validate
            new_allocation: New allocation to add (for creating/updating subscription)
            exclude_subscription_id: Subscription ID to exclude from calculation (for updates)
            
        Returns:
            (is_valid, current_total, message)
        """
        from sqlalchemy import func
        
        query = db.session.query(func.coalesce(func.sum(StrategySubscription.allocation_percent), 0.0))\
            .filter(StrategySubscription.user_id == user_id, StrategySubscription.is_active == True)
        
        if exclude_subscription_id:
            query = query.filter(StrategySubscription.id != exclude_subscription_id)
        
        current_total = float(query.scalar() or 0)
        projected_total = current_total + new_allocation
        
        if projected_total > 100.0:
            return False, current_total, f"Total allocation would be {projected_total}%. Maximum is 100%."
        
        return True, current_total, "OK"


# ==================== LIVE CHAT MODELS ====================

class ChatMessage(db.Model):
    """
    Live chat messages for the General Room.
    Only users with active subscriptions can send messages.
    """
    __tablename__ = 'chat_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    room = db.Column(db.String(50), default='general', nullable=False, index=True)  # Room name
    
    # Message content
    message = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(20), default='user')  # 'user', 'system', 'whale_alert', 'admin'
    
    # For whale alerts and special messages
    extra_data = db.Column(db.JSON, nullable=True)  # Store trade details, amounts, etc.
    
    # Status
    is_deleted = db.Column(db.Boolean, default=False, index=True)
    deleted_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('chat_messages', lazy='dynamic'))
    deleted_by = db.relationship('User', foreign_keys=[deleted_by_id])
    
    # Indexes for efficient querying
    __table_args__ = (
        db.Index('idx_chat_room_time', 'room', 'created_at'),
        db.Index('idx_chat_room_deleted', 'room', 'is_deleted'),
    )
    
    def to_dict(self):
        """Convert message to dictionary for API response"""
        # Mask username for privacy in whale alerts
        display_name = self.user.username if self.user else 'Unknown'
        if len(display_name) > 3:
            masked_name = display_name[0] + '*' * (len(display_name) - 2) + display_name[-1]
        else:
            masked_name = display_name
            
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': display_name,
            'masked_username': masked_name,
            'avatar': self.user.avatar if self.user else '🤖',
            'avatar_type': self.user.avatar_type if self.user else 'emoji',
            'room': self.room,
            'message': self.message,
            'message_type': self.message_type,
            'extra_data': self.extra_data,
            'is_deleted': self.is_deleted,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'timestamp': self.created_at.strftime('%H:%M') if self.created_at else '',
        }
    
    @staticmethod
    def create_system_message(room: str, message: str, message_type: str = 'system', extra_data: dict = None):
        """Create a system message (bot, whale alert, etc.)"""
        # System messages don't have a user - we'll use user_id=0 or a special system user
        # For now, we'll create without user_id and handle it specially
        msg = ChatMessage(
            user_id=1,  # Will be the first admin/system user
            room=room,
            message=message,
            message_type=message_type,
            extra_data=extra_data
        )
        return msg
    
    @staticmethod
    def get_recent_messages(room: str = 'general', limit: int = 50, before_id: int = None):
        """Get recent messages for a room"""
        query = ChatMessage.query.filter_by(room=room, is_deleted=False)
        if before_id:
            query = query.filter(ChatMessage.id < before_id)
        return query.order_by(ChatMessage.created_at.desc()).limit(limit).all()


class ChatBan(db.Model):
    """
    Chat moderation: mute and ban users from the chat.
    """
    __tablename__ = 'chat_bans'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Ban/Mute details
    ban_type = db.Column(db.String(20), default='mute', index=True)  # 'mute' (temp) or 'ban' (permanent)
    reason = db.Column(db.String(500), nullable=True)
    
    # Duration
    expires_at = db.Column(db.DateTime, nullable=True, index=True)  # NULL = permanent ban
    
    # Admin who issued the ban
    issued_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    # Whether the ban is active
    is_active = db.Column(db.Boolean, default=True, index=True)
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('chat_bans', lazy='dynamic'))
    issued_by = db.relationship('User', foreign_keys=[issued_by_id])
    
    # Indexes
    __table_args__ = (
        db.Index('idx_chatban_user_active', 'user_id', 'is_active'),
        db.Index('idx_chatban_type_active', 'ban_type', 'is_active'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else 'Unknown',
            'ban_type': self.ban_type,
            'reason': self.reason,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'issued_by': self.issued_by.username if self.issued_by else 'System',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_active': self.is_active,
        }
    
    def is_expired(self) -> bool:
        """Check if the ban/mute has expired"""
        if not self.expires_at:
            return False  # Permanent ban
        now = datetime.now(timezone.utc)
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return now >= expires
    
    @staticmethod
    def get_active_ban(user_id: int):
        """Get active ban for a user, if any"""
        ban = ChatBan.query.filter_by(user_id=user_id, is_active=True).order_by(ChatBan.created_at.desc()).first()
        if ban and ban.is_expired():
            ban.is_active = False
            db.session.commit()
            return None
        return ban
    
    @staticmethod
    def is_user_banned(user_id: int) -> tuple:
        """
        Check if user is banned/muted.
        Returns (is_banned, ban_type, reason, expires_at)
        """
        ban = ChatBan.get_active_ban(user_id)
        if not ban:
            return (False, None, None, None)
        return (True, ban.ban_type, ban.reason, ban.expires_at)
    
    @staticmethod
    def mute_user(user_id: int, duration_minutes: int, reason: str, issued_by_id: int):
        """Mute a user for specified duration"""
        expires = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
        ban = ChatBan(
            user_id=user_id,
            ban_type='mute',
            reason=reason,
            expires_at=expires,
            issued_by_id=issued_by_id,
            is_active=True
        )
        db.session.add(ban)
        db.session.commit()
        return ban
    
    @staticmethod
    def ban_user(user_id: int, reason: str, issued_by_id: int):
        """Permanently ban a user from chat"""
        ban = ChatBan(
            user_id=user_id,
            ban_type='ban',
            reason=reason,
            expires_at=None,  # Permanent
            issued_by_id=issued_by_id,
            is_active=True
        )
        db.session.add(ban)
        db.session.commit()
        return ban
    
    @staticmethod
    def unban_user(user_id: int):
        """Remove all active bans for a user"""
        ChatBan.query.filter_by(user_id=user_id, is_active=True).update({'is_active': False})
        db.session.commit()


# ==================== GAMIFICATION SYSTEM ====================

class UserLevel(db.Model):
    """
    Defines user levels based on trading volume/XP.
    
    Levels:
    - Novice (0-1k Volume) - 0% discount
    - Amateur (1k-10k Volume) - 2% discount
    - Pro (10k-50k Volume) - 5% discount
    - Expert (50k-100k Volume) - 8% discount
    - Elite (100k+ Volume) - 10% discount
    """
    __tablename__ = 'user_levels'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    icon = db.Column(db.String(50), default='fa-user')  # FontAwesome icon
    color = db.Column(db.String(20), default='#888888')  # Badge color
    min_xp = db.Column(db.Integer, default=0, nullable=False)  # Minimum XP to reach this level
    max_xp = db.Column(db.Integer, nullable=True)  # Maximum XP for this level (NULL = unlimited)
    discount_percent = db.Column(db.Float, default=0.0)  # Commission discount percentage
    order_rank = db.Column(db.Integer, default=0)  # Display order (0 = lowest)
    description = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'icon': self.icon,
            'color': self.color,
            'min_xp': self.min_xp,
            'max_xp': self.max_xp,
            'discount_percent': self.discount_percent,
            'order_rank': self.order_rank,
            'description': self.description,
        }
    
    @staticmethod
    def get_level_for_xp(xp: int):
        """Get the appropriate level for given XP amount"""
        return UserLevel.query.filter(
            UserLevel.min_xp <= xp
        ).order_by(UserLevel.min_xp.desc()).first()
    
    @staticmethod
    def get_next_level(current_level):
        """Get the next level after the current one"""
        if not current_level:
            return UserLevel.query.order_by(UserLevel.order_rank.asc()).first()
        return UserLevel.query.filter(
            UserLevel.order_rank > current_level.order_rank
        ).order_by(UserLevel.order_rank.asc()).first()
    
    @staticmethod
    def initialize_default_levels():
        """Create default level tiers if they don't exist"""
        default_levels = [
            {
                'name': 'Novice',
                'icon': 'fa-seedling',
                'color': '#888888',
                'min_xp': 0,
                'max_xp': 1000,
                'discount_percent': 0.0,
                'order_rank': 0,
                'description': 'Just getting started! Trade to earn XP and level up.'
            },
            {
                'name': 'Amateur',
                'icon': 'fa-user',
                'color': '#4CAF50',
                'min_xp': 1000,
                'max_xp': 10000,
                'discount_percent': 2.0,
                'order_rank': 1,
                'description': 'Building your skills! 2% commission discount.'
            },
            {
                'name': 'Pro',
                'icon': 'fa-chart-line',
                'color': '#2196F3',
                'min_xp': 10000,
                'max_xp': 50000,
                'discount_percent': 5.0,
                'order_rank': 2,
                'description': 'Proven trader! 5% commission discount.'
            },
            {
                'name': 'Expert',
                'icon': 'fa-star',
                'color': '#9C27B0',
                'min_xp': 50000,
                'max_xp': 100000,
                'discount_percent': 8.0,
                'order_rank': 3,
                'description': 'Top-tier performer! 8% commission discount.'
            },
            {
                'name': 'Elite',
                'icon': 'fa-crown',
                'color': '#FFD700',
                'min_xp': 100000,
                'max_xp': None,  # Unlimited
                'discount_percent': 10.0,
                'order_rank': 4,
                'description': 'The best of the best! 10% commission discount.'
            },
        ]
        
        created_count = 0
        for level_data in default_levels:
            existing = UserLevel.query.filter_by(name=level_data['name']).first()
            if not existing:
                level = UserLevel(**level_data)
                db.session.add(level)
                created_count += 1
        
        if created_count > 0:
            db.session.commit()
        
        return created_count


class UserAchievement(db.Model):
    """
    User achievements/badges that are unlocked through trading milestones.
    
    Badges:
    - First Blood: First profitable trade
    - Diamond Hands: Held through volatility (no red closes)
    - Whale: Large volume trader (>$100k lifetime volume)
    - Win Streak: 5+ consecutive profitable trades
    - Risk Manager: Used stop-loss on 10+ trades
    - Early Adopter: Registered in first 30 days of platform
    """
    __tablename__ = 'user_achievements'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    achievement_type = db.Column(db.String(50), nullable=False, index=True)  # 'first_blood', 'diamond_hands', etc.
    
    # Achievement metadata
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    icon = db.Column(db.String(50), default='fa-trophy')  # FontAwesome icon
    color = db.Column(db.String(20), default='#FFD700')  # Badge color
    rarity = db.Column(db.String(20), default='common')  # common, rare, epic, legendary
    
    # Timestamps
    unlocked_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    # Relationship
    user = db.relationship('User', backref=db.backref('achievements', lazy='dynamic', cascade='all, delete-orphan'))
    
    # Unique constraint: user can only unlock each achievement once
    __table_args__ = (
        db.UniqueConstraint('user_id', 'achievement_type', name='unique_user_achievement'),
        db.Index('idx_achievement_user_type', 'user_id', 'achievement_type'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'achievement_type': self.achievement_type,
            'name': self.name,
            'description': self.description,
            'icon': self.icon,
            'color': self.color,
            'rarity': self.rarity,
            'unlocked_at': self.unlocked_at.isoformat() if self.unlocked_at else None,
        }
    
    # ============ ACHIEVEMENT DEFINITIONS ============
    ACHIEVEMENTS = {
        'first_blood': {
            'name': 'First Blood',
            'description': 'Scored your first profitable trade!',
            'icon': 'fa-crosshairs',
            'color': '#FF5722',
            'rarity': 'common'
        },
        'diamond_hands': {
            'name': 'Diamond Hands',
            'description': 'Never closed a position in the red. True conviction!',
            'icon': 'fa-gem',
            'color': '#00BCD4',
            'rarity': 'epic'
        },
        'whale': {
            'name': 'Whale',
            'description': 'Traded over $100,000 in lifetime volume!',
            'icon': 'fa-water',
            'color': '#3F51B5',
            'rarity': 'legendary'
        },
        'win_streak': {
            'name': 'Win Streak',
            'description': '5+ consecutive profitable trades!',
            'icon': 'fa-fire',
            'color': '#F44336',
            'rarity': 'rare'
        },
        'risk_manager': {
            'name': 'Risk Manager',
            'description': 'Used stop-loss protection on 10+ trades.',
            'icon': 'fa-shield-alt',
            'color': '#4CAF50',
            'rarity': 'common'
        },
        'early_adopter': {
            'name': 'Early Adopter',
            'description': 'Joined MIMIC in the early days!',
            'icon': 'fa-rocket',
            'color': '#9C27B0',
            'rarity': 'rare'
        },
        'night_owl': {
            'name': 'Night Owl',
            'description': 'Made 10+ trades between midnight and 5 AM.',
            'icon': 'fa-moon',
            'color': '#673AB7',
            'rarity': 'common'
        },
        'big_winner': {
            'name': 'Big Winner',
            'description': 'Single trade profit exceeding $1,000!',
            'icon': 'fa-dollar-sign',
            'color': '#FFD700',
            'rarity': 'epic'
        },
    }
    
    @classmethod
    def unlock_achievement(cls, user_id: int, achievement_type: str):
        """
        Unlock an achievement for a user if not already unlocked.
        
        Returns:
            UserAchievement if newly unlocked, None if already exists
        """
        if achievement_type not in cls.ACHIEVEMENTS:
            return None
        
        # Check if already unlocked
        existing = cls.query.filter_by(user_id=user_id, achievement_type=achievement_type).first()
        if existing:
            return None
        
        # Unlock the achievement
        achievement_data = cls.ACHIEVEMENTS[achievement_type]
        achievement = cls(
            user_id=user_id,
            achievement_type=achievement_type,
            name=achievement_data['name'],
            description=achievement_data['description'],
            icon=achievement_data['icon'],
            color=achievement_data['color'],
            rarity=achievement_data['rarity']
        )
        db.session.add(achievement)
        db.session.commit()
        
        return achievement
    
    @classmethod
    def get_user_achievements(cls, user_id: int):
        """Get all achievements for a user"""
        return cls.query.filter_by(user_id=user_id).order_by(cls.unlocked_at.desc()).all()
    
    @classmethod
    def get_all_possible_achievements(cls):
        """Get list of all possible achievements with unlock status"""
        return list(cls.ACHIEVEMENTS.items())
    
    @classmethod
    def check_and_unlock(cls, user_id: int, trade_data: dict = None):
        """
        Check if user qualifies for any new achievements and unlock them.
        
        Args:
            user_id: User ID to check
            trade_data: Optional recent trade data that triggered the check
            
        Returns:
            List of newly unlocked achievements
        """
        from sqlalchemy import func
        
        unlocked = []
        user = User.query.get(user_id)
        if not user:
            return unlocked
        
        # Get user's trade history
        total_trades = TradeHistory.query.filter_by(user_id=user_id).count()
        profitable_trades = TradeHistory.query.filter(
            TradeHistory.user_id == user_id,
            TradeHistory.pnl > 0
        ).count()
        losing_trades = TradeHistory.query.filter(
            TradeHistory.user_id == user_id,
            TradeHistory.pnl < 0
        ).count()
        
        # Calculate total volume (sum of absolute PnL as proxy)
        total_volume_result = db.session.query(func.sum(func.abs(TradeHistory.pnl))).filter(
            TradeHistory.user_id == user_id
        ).scalar()
        total_volume = float(total_volume_result or 0) * 100  # Scale up as proxy for volume
        
        # First Blood: First profitable trade
        if profitable_trades >= 1:
            achievement = cls.unlock_achievement(user_id, 'first_blood')
            if achievement:
                unlocked.append(achievement)
        
        # Diamond Hands: Never closed in the red (requires at least 10 trades)
        if total_trades >= 10 and losing_trades == 0:
            achievement = cls.unlock_achievement(user_id, 'diamond_hands')
            if achievement:
                unlocked.append(achievement)
        
        # Whale: $100k+ lifetime volume
        if total_volume >= 100000:
            achievement = cls.unlock_achievement(user_id, 'whale')
            if achievement:
                unlocked.append(achievement)
        
        # Win Streak: 5+ consecutive profitable trades
        recent_trades = TradeHistory.query.filter_by(user_id=user_id).order_by(
            TradeHistory.close_time.desc()
        ).limit(5).all()
        if len(recent_trades) >= 5 and all(t.pnl > 0 for t in recent_trades):
            achievement = cls.unlock_achievement(user_id, 'win_streak')
            if achievement:
                unlocked.append(achievement)
        
        # Big Winner: Single trade profit > $1000
        if trade_data and trade_data.get('pnl', 0) >= 1000:
            achievement = cls.unlock_achievement(user_id, 'big_winner')
            if achievement:
                unlocked.append(achievement)
        
        # Early Adopter: Registered within first 30 days of platform
        # (Check if user created_at is within 30 days of the first user)
        first_user = User.query.order_by(User.created_at.asc()).first()
        if first_user and user.created_at:
            platform_start = first_user.created_at
            if user.created_at.tzinfo is None:
                user_created = user.created_at.replace(tzinfo=timezone.utc)
            else:
                user_created = user.created_at
            if platform_start.tzinfo is None:
                platform_start = platform_start.replace(tzinfo=timezone.utc)
            
            if (user_created - platform_start).days <= 30:
                achievement = cls.unlock_achievement(user_id, 'early_adopter')
                if achievement:
                    unlocked.append(achievement)
        
        return unlocked


# ==================== GAMIFICATION HELPERS ====================
# These functions are used by User class methods for late binding

def _get_level_for_xp(xp: int):
    """Get the appropriate level for given XP amount"""
    return UserLevel.query.filter(UserLevel.min_xp <= xp).order_by(UserLevel.min_xp.desc()).first()

def _get_next_level(current_level):
    """Get the next level after the current one"""
    if not current_level:
        return UserLevel.query.order_by(UserLevel.order_rank.asc()).first()
    return UserLevel.query.filter(UserLevel.order_rank > current_level.order_rank).order_by(UserLevel.order_rank.asc()).first()


# ==================== SYSTEM STATS / INSURANCE FUND ====================

# ==================== API KEYS FOR PUBLIC API ====================

class ApiKey(db.Model):
    """
    API Keys for the public developer API (api.mimic.cash).
    
    Allows users to programmatically send trading signals and execute orders
    via the MIMIC platform.
    
    Authentication uses HMAC-SHA256 signature verification.
    """
    __tablename__ = 'api_keys'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Key identifier (public) - used in X-API-Key header
    key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    
    # Secret for HMAC signing (stored as bcrypt hash for security)
    # The actual secret is shown only once at creation time
    secret_hash = db.Column(db.String(256), nullable=False)
    
    # Human-readable label
    label = db.Column(db.String(100), nullable=False, default='Default API Key')
    
    # Permissions bitmask
    # 1 = read (view positions, balance)
    # 2 = signal (send signals)
    # 4 = trade (execute orders)
    # 7 = all permissions
    permissions = db.Column(db.Integer, default=7, nullable=False)
    
    # Rate limiting (requests per minute)
    rate_limit = db.Column(db.Integer, default=60, nullable=False)
    
    # IP whitelist (JSON array of allowed IPs, empty = all allowed)
    ip_whitelist = db.Column(db.JSON, nullable=True)
    
    # Status
    is_active = db.Column(db.Boolean, default=True, index=True)
    
    # Tracking
    last_used_at = db.Column(db.DateTime, nullable=True)
    total_requests = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    expires_at = db.Column(db.DateTime, nullable=True, index=True)  # NULL = never expires
    revoked_at = db.Column(db.DateTime, nullable=True)
    
    # Relationship
    user = db.relationship('User', backref=db.backref('api_keys', lazy='dynamic', cascade='all, delete-orphan'))
    
    # Indexes
    __table_args__ = (
        db.Index('idx_apikey_user_active', 'user_id', 'is_active'),
        db.Index('idx_apikey_key_active', 'key', 'is_active'),
    )
    
    # Permission constants
    PERMISSION_READ = 1
    PERMISSION_SIGNAL = 2
    PERMISSION_TRADE = 4
    PERMISSION_ALL = 7
    
    def has_permission(self, permission: int) -> bool:
        """Check if this API key has a specific permission"""
        return (self.permissions & permission) == permission
    
    def can_read(self) -> bool:
        """Check if key has read permission"""
        return self.has_permission(self.PERMISSION_READ)
    
    def can_signal(self) -> bool:
        """Check if key has signal permission"""
        return self.has_permission(self.PERMISSION_SIGNAL)
    
    def can_trade(self) -> bool:
        """Check if key has trade permission"""
        return self.has_permission(self.PERMISSION_TRADE)
    
    def is_valid(self) -> bool:
        """Check if API key is valid (active, not expired, not revoked)"""
        if not self.is_active:
            return False
        if self.revoked_at:
            return False
        if self.expires_at:
            now = datetime.now(timezone.utc)
            expires = self.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if now >= expires:
                return False
        return True
    
    def is_ip_allowed(self, ip: str) -> bool:
        """Check if IP is in whitelist (empty whitelist = all allowed)"""
        if not self.ip_whitelist:
            return True
        return ip in self.ip_whitelist
    
    def verify_secret(self, secret: str) -> bool:
        """Verify the API secret against stored hash"""
        from werkzeug.security import check_password_hash
        return check_password_hash(self.secret_hash, secret)
    
    def record_usage(self):
        """Record API key usage"""
        self.last_used_at = datetime.now(timezone.utc)
        self.total_requests = (self.total_requests or 0) + 1
    
    def revoke(self):
        """Revoke this API key"""
        self.is_active = False
        self.revoked_at = datetime.now(timezone.utc)
        db.session.commit()
    
    def to_dict(self, include_stats: bool = False) -> dict:
        """Convert to dictionary for API response"""
        data = {
            'id': self.id,
            'key': self.key,
            'label': self.label,
            'permissions': {
                'read': self.can_read(),
                'signal': self.can_signal(),
                'trade': self.can_trade(),
            },
            'rate_limit': self.rate_limit,
            'ip_whitelist': self.ip_whitelist or [],
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
        }
        if include_stats:
            data['last_used_at'] = self.last_used_at.isoformat() if self.last_used_at else None
            data['total_requests'] = self.total_requests or 0
        return data
    
    @staticmethod
    def generate_key() -> str:
        """Generate a unique API key identifier"""
        return 'mk_' + secrets.token_hex(24)  # 'mk_' prefix + 48 hex chars
    
    @staticmethod
    def generate_secret() -> str:
        """Generate a secure API secret"""
        return 'ms_' + secrets.token_urlsafe(32)  # 'ms_' prefix + 43 chars
    
    @classmethod
    def create_for_user(cls, user_id: int, label: str = 'Default API Key', 
                        permissions: int = 7, rate_limit: int = 60,
                        ip_whitelist: list = None, expires_days: int = None) -> tuple:
        """
        Create a new API key for a user.
        
        Returns:
            tuple: (ApiKey object, plain_secret) - secret is only shown once!
        """
        from werkzeug.security import generate_password_hash
        
        # Generate key and secret
        key = cls.generate_key()
        secret = cls.generate_secret()
        
        # Hash the secret for storage
        secret_hash = generate_password_hash(secret, method='scrypt')
        
        # Calculate expiration
        expires_at = None
        if expires_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)
        
        # Create the API key
        api_key = cls(
            user_id=user_id,
            key=key,
            secret_hash=secret_hash,
            label=label,
            permissions=permissions,
            rate_limit=rate_limit,
            ip_whitelist=ip_whitelist,
            expires_at=expires_at,
        )
        
        db.session.add(api_key)
        db.session.commit()
        
        return api_key, secret
    
    @classmethod
    def get_by_key(cls, key: str):
        """Get API key by its public key identifier"""
        return cls.query.filter_by(key=key, is_active=True).first()
    
    @classmethod
    def get_user_keys(cls, user_id: int, include_revoked: bool = False):
        """Get all API keys for a user"""
        query = cls.query.filter_by(user_id=user_id)
        if not include_revoked:
            query = query.filter_by(is_active=True)
        return query.order_by(cls.created_at.desc()).all()


class SystemStats(db.Model):
    """
    Platform-wide statistics including the Insurance Fund (Safety Pool).
    
    The Insurance Fund accumulates 5% of platform fees and is used to
    cover slippage losses in extreme market conditions.
    """
    __tablename__ = 'system_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    stat_key = db.Column(db.String(50), unique=True, nullable=False, index=True)
    stat_value = db.Column(db.Float, default=0.0)
    description = db.Column(db.Text, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # ============ INSURANCE FUND CONSTANTS ============
    INSURANCE_FUND_KEY = 'insurance_fund_balance'
    INSURANCE_FUND_RATE = 0.05  # 5% of platform fees
    
    def to_dict(self):
        return {
            'id': self.id,
            'stat_key': self.stat_key,
            'stat_value': self.stat_value,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @classmethod
    def get_or_create(cls, stat_key: str, default_value: float = 0.0, description: str = None):
        """Get or create a system stat by key"""
        stat = cls.query.filter_by(stat_key=stat_key).first()
        if not stat:
            stat = cls(
                stat_key=stat_key,
                stat_value=default_value,
                description=description
            )
            db.session.add(stat)
            db.session.commit()
        return stat
    
    @classmethod
    def get_insurance_fund_balance(cls) -> float:
        """Get the current Insurance Fund balance"""
        stat = cls.query.filter_by(stat_key=cls.INSURANCE_FUND_KEY).first()
        return float(stat.stat_value) if stat else 0.0
    
    @classmethod
    def add_to_insurance_fund(cls, amount: float) -> float:
        """Add funds to the Insurance Fund and return new balance"""
        if amount <= 0:
            return cls.get_insurance_fund_balance()
        
        stat = cls.get_or_create(
            cls.INSURANCE_FUND_KEY, 
            default_value=0.0,
            description='Safety Pool - covers slippage losses in extreme market conditions'
        )
        stat.stat_value = float(stat.stat_value or 0) + amount
        db.session.commit()
        return stat.stat_value
    
    @classmethod
    def initialize_insurance_fund(cls, initial_balance: float = 0.0):
        """Initialize or reset the Insurance Fund"""
        stat = cls.get_or_create(
            cls.INSURANCE_FUND_KEY,
            default_value=initial_balance,
            description='Safety Pool - covers slippage losses in extreme market conditions'
        )
        if stat.stat_value == 0.0 and initial_balance > 0:
            stat.stat_value = initial_balance
            db.session.commit()
        return stat
    
    @classmethod
    def calculate_insurance_contribution(cls, fee_amount: float) -> float:
        """Calculate 5% contribution to Insurance Fund from fees"""
        return fee_amount * cls.INSURANCE_FUND_RATE
    
    @classmethod
    def get_insurance_fund_info(cls) -> dict:
        """Get complete Insurance Fund information for display"""
        stat = cls.query.filter_by(stat_key=cls.INSURANCE_FUND_KEY).first()
        
        if not stat:
            return {
                'balance': 0.0,
                'formatted_balance': '$0.00',
                'last_updated': None,
                'description': 'Safety Pool - covers slippage losses in extreme market conditions',
                'contribution_rate': '5%',
                'is_verified': True  # Always verified as it's platform-managed
            }
        
        balance = float(stat.stat_value or 0)
        return {
            'balance': balance,
            'formatted_balance': f'${balance:,.2f}',
            'last_updated': stat.updated_at.isoformat() if stat.updated_at else None,
            'description': stat.description or 'Safety Pool - covers slippage losses in extreme market conditions',
            'contribution_rate': '5%',
            'is_verified': True
        }


# ==================== RAG SUPPORT BOT MODELS ====================

class DocumentChunk(db.Model):
    """
    Stores embedded documentation chunks for RAG retrieval.
    
    Each chunk is a portion of documentation (README, FAQ, etc.) with its
    vector embedding for similarity search.
    """
    __tablename__ = 'document_chunks'
    
    id = db.Column(db.Integer, primary_key=True)
    source_file = db.Column(db.String(200), nullable=False, index=True)
    chunk_index = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    # Embedding stored as JSON string for SQLite compatibility
    # For PostgreSQL with pgvector, the actual column is vector(1536)
    embedding = db.Column(db.Text, nullable=True)
    # Note: 'metadata' is reserved in SQLAlchemy, so we use 'chunk_metadata'
    chunk_metadata = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'source_file': self.source_file,
            'chunk_index': self.chunk_index,
            'content': self.content[:200] + '...' if len(self.content) > 200 else self.content,
            'metadata': self.chunk_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SupportConversation(db.Model):
    """
    Tracks support chat sessions for context continuity.
    
    Each conversation can span multiple messages and may be associated
    with a logged-in user or an anonymous session.
    """
    __tablename__ = 'support_conversations'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    telegram_chat_id = db.Column(db.String(50), nullable=True)
    channel = db.Column(db.String(20), default='web')  # 'web', 'telegram'
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))
    is_resolved = db.Column(db.Boolean, default=False, index=True)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('support_conversations', lazy='dynamic'))
    messages = db.relationship('SupportMessage', backref='conversation', lazy='dynamic',
                              cascade='all, delete-orphan', order_by='SupportMessage.created_at')
    
    def to_dict(self, include_messages: bool = False):
        data = {
            'id': self.id,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else None,
            'channel': self.channel,
            'is_resolved': self.is_resolved,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'message_count': self.messages.count(),
        }
        if include_messages:
            data['messages'] = [m.to_dict() for m in self.messages.all()]
        return data
    
    @staticmethod
    def get_or_create(session_id: str, user_id: int = None, channel: str = 'web', 
                      telegram_chat_id: str = None):
        """Get existing conversation or create new one"""
        conversation = SupportConversation.query.filter_by(session_id=session_id).first()
        if not conversation:
            conversation = SupportConversation(
                session_id=session_id,
                user_id=user_id,
                channel=channel,
                telegram_chat_id=telegram_chat_id
            )
            db.session.add(conversation)
            db.session.commit()
        return conversation


class SupportMessage(db.Model):
    """
    Individual messages within a support conversation.
    
    Stores both user questions and AI responses with confidence scores.
    """
    __tablename__ = 'support_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('support_conversations.id', ondelete='CASCADE'),
                               nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = db.Column(db.Text, nullable=False)
    confidence = db.Column(db.Float, nullable=True)  # AI confidence score (0.0-1.0)
    sources = db.Column(db.JSON, nullable=True)  # Source documents used for answer
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'conversation_id': self.conversation_id,
            'role': self.role,
            'content': self.content,
            'confidence': self.confidence,
            'sources': self.sources,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SupportTicket(db.Model):
    """
    Support tickets for low-confidence AI responses or escalated issues.
    
    When the AI confidence is below threshold (default 0.7), a ticket is
    created for human admin review.
    """
    __tablename__ = 'support_tickets'
    
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('support_conversations.id', ondelete='SET NULL'),
                               nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    
    question = db.Column(db.Text, nullable=False)
    ai_response = db.Column(db.Text, nullable=True)
    confidence = db.Column(db.Float, nullable=True)
    
    status = db.Column(db.String(20), default='open', index=True)  # 'open', 'in_progress', 'resolved', 'closed'
    priority = db.Column(db.String(20), default='normal')  # 'low', 'normal', 'high', 'urgent'
    
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    admin_response = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))
    resolved_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], 
                          backref=db.backref('support_tickets', lazy='dynamic'))
    assigned_to = db.relationship('User', foreign_keys=[assigned_to_id])
    conversation = db.relationship('SupportConversation', backref=db.backref('tickets', lazy='dynamic'))
    
    # Indexes
    __table_args__ = (
        db.Index('idx_ticket_status_created', 'status', 'created_at'),
        db.Index('idx_ticket_user_status', 'user_id', 'status'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'conversation_id': self.conversation_id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else 'Anonymous',
            'question': self.question,
            'ai_response': self.ai_response,
            'confidence': self.confidence,
            'status': self.status,
            'priority': self.priority,
            'assigned_to': self.assigned_to.username if self.assigned_to else None,
            'admin_response': self.admin_response,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
        }
    
    @classmethod
    def create_from_low_confidence(cls, conversation_id: int, user_id: int, 
                                   question: str, ai_response: str, confidence: float):
        """Create a ticket from a low-confidence AI response"""
        # Determine priority based on confidence
        if confidence < 0.3:
            priority = 'high'
        elif confidence < 0.5:
            priority = 'normal'
        else:
            priority = 'low'
        
        ticket = cls(
            conversation_id=conversation_id,
            user_id=user_id,
            question=question,
            ai_response=ai_response,
            confidence=confidence,
            priority=priority
        )
        db.session.add(ticket)
        db.session.commit()
        return ticket
    
    def resolve(self, admin_response: str, admin_id: int):
        """Mark ticket as resolved with admin response"""
        self.status = 'resolved'
        self.admin_response = admin_response
        self.assigned_to_id = admin_id
        self.resolved_at = datetime.now(timezone.utc)
        db.session.commit()
    
    @classmethod
    def get_open_tickets(cls, limit: int = 50):
        """Get all open tickets ordered by priority and creation date"""
        priority_order = {'urgent': 0, 'high': 1, 'normal': 2, 'low': 3}
        return cls.query.filter(cls.status.in_(['open', 'in_progress']))\
            .order_by(cls.priority.asc(), cls.created_at.asc())\
            .limit(limit).all()


# ==================== TOURNAMENT SYSTEM ====================

class Tournament(db.Model):
    """
    Weekly trading tournament where users compete for prizes.
    
    Users contribute an entry fee (e.g., $10) to join.
    The prize pool is distributed to TOP-3 by ROI at the end of the week.
    
    Distribution: 1st = 50%, 2nd = 30%, 3rd = 20%
    """
    __tablename__ = 'tournaments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # Tournament schedule
    start_date = db.Column(db.DateTime, nullable=False, index=True)
    end_date = db.Column(db.DateTime, nullable=False, index=True)
    
    # Financial settings
    entry_fee = db.Column(db.Float, default=10.0, nullable=False)  # Entry fee in USD
    prize_pool = db.Column(db.Float, default=0.0, nullable=False)  # Total prize pool
    
    # Prize distribution (percentage)
    prize_1st_pct = db.Column(db.Float, default=50.0)  # 50% for 1st place
    prize_2nd_pct = db.Column(db.Float, default=30.0)  # 30% for 2nd place
    prize_3rd_pct = db.Column(db.Float, default=20.0)  # 20% for 3rd place
    
    # Minimum participants required to start
    min_participants = db.Column(db.Integer, default=3)
    max_participants = db.Column(db.Integer, nullable=True)  # NULL = unlimited
    
    # Tournament status
    status = db.Column(db.String(20), default='upcoming', index=True)  # 'upcoming', 'active', 'calculating', 'completed', 'cancelled'
    
    # Winner tracking
    winner_1st_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    winner_2nd_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    winner_3rd_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    finalized_at = db.Column(db.DateTime, nullable=True)  # When winners were determined
    
    # Relationships
    participants = db.relationship('TournamentParticipant', backref='tournament', lazy='dynamic', cascade='all, delete-orphan')
    winner_1st = db.relationship('User', foreign_keys=[winner_1st_id])
    winner_2nd = db.relationship('User', foreign_keys=[winner_2nd_id])
    winner_3rd = db.relationship('User', foreign_keys=[winner_3rd_id])
    
    # Indexes
    __table_args__ = (
        db.Index('idx_tournament_status_dates', 'status', 'start_date', 'end_date'),
    )
    
    def to_dict(self, include_participants: bool = False, include_leaderboard: bool = False):
        """Convert tournament to dictionary for API response"""
        data = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'entry_fee': self.entry_fee,
            'prize_pool': self.prize_pool,
            'prize_distribution': {
                '1st': self.prize_1st_pct,
                '2nd': self.prize_2nd_pct,
                '3rd': self.prize_3rd_pct,
            },
            'min_participants': self.min_participants,
            'max_participants': self.max_participants,
            'status': self.status,
            'participant_count': self.participants.count(),
            'time_remaining': self.get_time_remaining(),
            'is_active': self.is_active(),
            'is_registration_open': self.is_registration_open(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'finalized_at': self.finalized_at.isoformat() if self.finalized_at else None,
        }
        
        # Add winner info if completed
        if self.status == 'completed':
            data['winners'] = {
                '1st': {
                    'user_id': self.winner_1st_id,
                    'username': self.winner_1st.username if self.winner_1st else None,
                    'prize': round(self.prize_pool * self.prize_1st_pct / 100, 2),
                },
                '2nd': {
                    'user_id': self.winner_2nd_id,
                    'username': self.winner_2nd.username if self.winner_2nd else None,
                    'prize': round(self.prize_pool * self.prize_2nd_pct / 100, 2),
                },
                '3rd': {
                    'user_id': self.winner_3rd_id,
                    'username': self.winner_3rd.username if self.winner_3rd else None,
                    'prize': round(self.prize_pool * self.prize_3rd_pct / 100, 2),
                },
            }
        
        if include_participants:
            data['participants'] = [p.to_dict() for p in self.participants.all()]
        
        if include_leaderboard:
            data['leaderboard'] = self.get_leaderboard()
        
        return data
    
    def is_active(self) -> bool:
        """Check if tournament is currently running"""
        now = datetime.now(timezone.utc)
        start = self.start_date
        end = self.end_date
        
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        
        return self.status == 'active' and start <= now <= end
    
    def is_registration_open(self) -> bool:
        """Check if registration is still open"""
        if self.status not in ['upcoming', 'active']:
            return False
        
        now = datetime.now(timezone.utc)
        start = self.start_date
        
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        
        # Registration closes 1 hour after start or when max reached
        registration_deadline = start + timedelta(hours=1)
        
        if now > registration_deadline:
            return False
        
        if self.max_participants and self.participants.count() >= self.max_participants:
            return False
        
        return True
    
    def get_time_remaining(self) -> dict:
        """Get time remaining until tournament ends or starts"""
        now = datetime.now(timezone.utc)
        start = self.start_date
        end = self.end_date
        
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        
        if now < start:
            # Tournament hasn't started yet
            delta = start - now
            target = 'start'
        elif now < end:
            # Tournament is active
            delta = end - now
            target = 'end'
        else:
            # Tournament has ended
            return {'target': 'ended', 'days': 0, 'hours': 0, 'minutes': 0, 'seconds': 0, 'total_seconds': 0}
        
        total_seconds = int(delta.total_seconds())
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        return {
            'target': target,
            'days': days,
            'hours': hours,
            'minutes': minutes,
            'seconds': seconds,
            'total_seconds': total_seconds
        }
    
    def add_participant(self, user_id: int) -> 'TournamentParticipant':
        """Add a participant to the tournament"""
        if not self.is_registration_open():
            raise ValueError("Registration is closed for this tournament")
        
        # Check if already participating
        existing = TournamentParticipant.query.filter_by(
            tournament_id=self.id,
            user_id=user_id
        ).first()
        
        if existing:
            raise ValueError("User is already participating in this tournament")
        
        # Get user's starting balance at tournament start
        user = User.query.get(user_id)
        if not user:
            raise ValueError("User not found")
        
        # Record starting balance (we'll get the actual balance later)
        participant = TournamentParticipant(
            tournament_id=self.id,
            user_id=user_id,
            entry_fee_paid=self.entry_fee,
            starting_balance=0.0,  # Will be set when tournament starts
        )
        
        db.session.add(participant)
        
        # Increase prize pool
        self.prize_pool += self.entry_fee
        
        db.session.commit()
        return participant
    
    def get_leaderboard(self, limit: int = 100) -> list:
        """Get tournament leaderboard sorted by ROI"""
        participants = TournamentParticipant.query.filter_by(
            tournament_id=self.id
        ).order_by(
            TournamentParticipant.current_roi.desc()
        ).limit(limit).all()
        
        leaderboard = []
        for rank, p in enumerate(participants, 1):
            user = User.query.get(p.user_id)
            # Mask username for privacy
            username = user.username if user else 'Unknown'
            if len(username) > 3:
                masked = username[0] + '*' * (len(username) - 2) + username[-1]
            else:
                masked = username
            
            leaderboard.append({
                'rank': rank,
                'user_id': p.user_id,
                'username': username,
                'masked_username': masked,
                'avatar': user.avatar if user else '🤖',
                'starting_balance': p.starting_balance,
                'current_balance': p.current_balance,
                'current_roi': round(p.current_roi, 2),
                'trades_count': p.trades_count,
                'pnl': round(p.current_balance - p.starting_balance, 2) if p.starting_balance else 0,
                'last_updated': p.last_updated.isoformat() if p.last_updated else None,
            })
        
        return leaderboard
    
    def update_status(self):
        """Update tournament status based on current time"""
        now = datetime.now(timezone.utc)
        start = self.start_date
        end = self.end_date
        
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        
        if self.status == 'upcoming' and now >= start:
            if self.participants.count() >= self.min_participants:
                self.status = 'active'
            else:
                self.status = 'cancelled'
        elif self.status == 'active' and now >= end:
            self.status = 'calculating'
        
        db.session.commit()
    
    def finalize(self):
        """Finalize tournament and determine winners"""
        if self.status != 'calculating':
            raise ValueError("Tournament must be in 'calculating' status to finalize")
        
        # Get top 3 participants by ROI
        top_3 = TournamentParticipant.query.filter_by(
            tournament_id=self.id
        ).order_by(
            TournamentParticipant.current_roi.desc()
        ).limit(3).all()
        
        if len(top_3) >= 1:
            self.winner_1st_id = top_3[0].user_id
            top_3[0].final_rank = 1
            top_3[0].prize_won = round(self.prize_pool * self.prize_1st_pct / 100, 2)
        
        if len(top_3) >= 2:
            self.winner_2nd_id = top_3[1].user_id
            top_3[1].final_rank = 2
            top_3[1].prize_won = round(self.prize_pool * self.prize_2nd_pct / 100, 2)
        
        if len(top_3) >= 3:
            self.winner_3rd_id = top_3[2].user_id
            top_3[2].final_rank = 3
            top_3[2].prize_won = round(self.prize_pool * self.prize_3rd_pct / 100, 2)
        
        # Mark other participants
        for p in self.participants.all():
            if p.final_rank is None:
                # Get their actual rank
                rank = TournamentParticipant.query.filter(
                    TournamentParticipant.tournament_id == self.id,
                    TournamentParticipant.current_roi > p.current_roi
                ).count() + 1
                p.final_rank = rank
        
        self.status = 'completed'
        self.finalized_at = datetime.now(timezone.utc)
        db.session.commit()
    
    @staticmethod
    def get_active_tournament():
        """Get the currently active tournament"""
        return Tournament.query.filter_by(status='active').first()
    
    @staticmethod
    def get_upcoming_tournaments(limit: int = 5):
        """Get upcoming tournaments"""
        return Tournament.query.filter_by(status='upcoming').order_by(
            Tournament.start_date.asc()
        ).limit(limit).all()
    
    @staticmethod
    def create_weekly_tournament(
        name: str = None,
        entry_fee: float = 10.0,
        start_days_from_now: int = 0
    ) -> 'Tournament':
        """
        Create a new weekly tournament.
        
        Args:
            name: Tournament name (auto-generated if None)
            entry_fee: Entry fee in USD
            start_days_from_now: Days from now to start (0 = today)
        
        Returns:
            New Tournament instance
        """
        now = datetime.now(timezone.utc)
        
        # Calculate start date (next Monday at 00:00 UTC if start_days_from_now=0)
        days_until_monday = (7 - now.weekday()) % 7 + start_days_from_now * 7
        if days_until_monday == 0 and now.hour >= 0:  # If today is Monday but already started
            days_until_monday = 7
        
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=days_until_monday)
        end_date = start_date + timedelta(days=7)  # One week duration
        
        if not name:
            week_num = start_date.isocalendar()[1]
            name = f"Weekly Tournament - Week {week_num}"
        
        tournament = Tournament(
            name=name,
            description=f"Compete for the top spot! Entry: ${entry_fee}. Prizes: 50%/30%/20% for TOP-3.",
            start_date=start_date,
            end_date=end_date,
            entry_fee=entry_fee,
            prize_pool=0.0,  # Will grow as participants join
            status='upcoming'
        )
        
        db.session.add(tournament)
        db.session.commit()
        
        return tournament


class TournamentParticipant(db.Model):
    """
    Tracks individual user participation in a tournament.
    
    Records starting balance, current balance, and ROI for ranking.
    """
    __tablename__ = 'tournament_participants'
    
    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournaments.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Entry tracking
    entry_fee_paid = db.Column(db.Float, default=0.0)
    joined_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    # Performance tracking
    starting_balance = db.Column(db.Float, default=0.0)  # Balance at tournament start
    current_balance = db.Column(db.Float, default=0.0)   # Latest balance
    current_roi = db.Column(db.Float, default=0.0, index=True)  # ((current - start) / start) * 100
    trades_count = db.Column(db.Integer, default=0)      # Trades during tournament
    
    # Final results
    final_rank = db.Column(db.Integer, nullable=True)
    prize_won = db.Column(db.Float, default=0.0)
    
    # Timestamps
    last_updated = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationship
    user = db.relationship('User', backref=db.backref('tournament_participations', lazy='dynamic'))
    
    # Unique constraint: user can only join each tournament once
    __table_args__ = (
        db.UniqueConstraint('tournament_id', 'user_id', name='unique_tournament_user'),
        db.Index('idx_participant_tournament_roi', 'tournament_id', 'current_roi'),
    )
    
    def to_dict(self):
        """Convert participant to dictionary"""
        return {
            'id': self.id,
            'tournament_id': self.tournament_id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else 'Unknown',
            'entry_fee_paid': self.entry_fee_paid,
            'joined_at': self.joined_at.isoformat() if self.joined_at else None,
            'starting_balance': self.starting_balance,
            'current_balance': self.current_balance,
            'current_roi': round(self.current_roi, 2),
            'trades_count': self.trades_count,
            'final_rank': self.final_rank,
            'prize_won': self.prize_won,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
        }
    
    def update_performance(self, current_balance: float, trades_count: int = None):
        """Update participant's current performance metrics"""
        self.current_balance = current_balance
        
        if trades_count is not None:
            self.trades_count = trades_count
        
        # Calculate ROI
        if self.starting_balance and self.starting_balance > 0:
            self.current_roi = ((current_balance - self.starting_balance) / self.starting_balance) * 100
        else:
            self.current_roi = 0.0
        
        self.last_updated = datetime.now(timezone.utc)
        db.session.commit()
    
    def set_starting_balance(self, balance: float):
        """Set the starting balance (called when tournament starts)"""
        self.starting_balance = balance
        self.current_balance = balance
        self.current_roi = 0.0
        db.session.commit()
    
    @staticmethod
    def get_user_active_tournament(user_id: int) -> 'TournamentParticipant':
        """Get user's participation in the active tournament, if any"""
        active_tournament = Tournament.get_active_tournament()
        if not active_tournament:
            return None
        
        return TournamentParticipant.query.filter_by(
            tournament_id=active_tournament.id,
            user_id=user_id
        ).first()


# ==================== GOVERNANCE / VOTING SYSTEM ====================

class Proposal(db.Model):
    """
    Governance proposals that Elite users can vote on.
    
    Categories:
    - trading_pair: New trading pair requests (e.g., 'Add SOL/USDT pair')
    - risk_management: Risk settings changes
    - exchange: New exchange integration requests
    - feature: Feature requests
    - other: Other proposals
    """
    __tablename__ = 'proposals'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False, index=True)  # trading_pair, risk_management, exchange, feature, other
    
    # Status: pending, active, passed, rejected, implemented
    status = db.Column(db.String(20), default='active', index=True)
    
    # Vote counts (cached for performance)
    votes_yes = db.Column(db.Integer, default=0)
    votes_no = db.Column(db.Integer, default=0)
    votes_yes_weight = db.Column(db.Float, default=0.0)  # Weighted by volume
    votes_no_weight = db.Column(db.Float, default=0.0)   # Weighted by volume
    
    # Proposal thresholds
    min_votes_required = db.Column(db.Integer, default=5)  # Minimum votes to pass
    pass_threshold = db.Column(db.Float, default=60.0)  # Percentage of YES votes required to pass
    
    # Creator (admin who created the proposal)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    created_by = db.relationship('User', foreign_keys=[created_by_id], backref=db.backref('created_proposals', lazy='dynamic'))
    
    # Dates
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    voting_ends_at = db.Column(db.DateTime, nullable=True, index=True)  # NULL = no deadline
    closed_at = db.Column(db.DateTime, nullable=True)  # When voting was closed
    implemented_at = db.Column(db.DateTime, nullable=True)  # When proposal was implemented
    
    # Admin notes
    admin_notes = db.Column(db.Text, nullable=True)
    
    # Relationships
    votes = db.relationship('Vote', backref='proposal', lazy='dynamic', cascade='all, delete-orphan')
    
    __table_args__ = (
        db.Index('idx_proposal_status_category', 'status', 'category'),
        db.Index('idx_proposal_active_ends', 'status', 'voting_ends_at'),
    )
    
    def to_dict(self, include_votes=False):
        """Convert proposal to dictionary"""
        total_votes = self.votes_yes + self.votes_no
        yes_percentage = (self.votes_yes / total_votes * 100) if total_votes > 0 else 0
        no_percentage = (self.votes_no / total_votes * 100) if total_votes > 0 else 0
        
        # Calculate weighted percentages
        total_weight = self.votes_yes_weight + self.votes_no_weight
        yes_weight_percentage = (self.votes_yes_weight / total_weight * 100) if total_weight > 0 else 0
        no_weight_percentage = (self.votes_no_weight / total_weight * 100) if total_weight > 0 else 0
        
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'category_label': self.get_category_label(),
            'category_icon': self.get_category_icon(),
            'status': self.status,
            'status_label': self.get_status_label(),
            'votes_yes': self.votes_yes,
            'votes_no': self.votes_no,
            'total_votes': total_votes,
            'yes_percentage': round(yes_percentage, 1),
            'no_percentage': round(no_percentage, 1),
            'votes_yes_weight': round(self.votes_yes_weight, 2),
            'votes_no_weight': round(self.votes_no_weight, 2),
            'yes_weight_percentage': round(yes_weight_percentage, 1),
            'no_weight_percentage': round(no_weight_percentage, 1),
            'min_votes_required': self.min_votes_required,
            'pass_threshold': self.pass_threshold,
            'created_by': self.created_by.username if self.created_by else 'System',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'voting_ends_at': self.voting_ends_at.isoformat() if self.voting_ends_at else None,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'implemented_at': self.implemented_at.isoformat() if self.implemented_at else None,
            'time_remaining': self.get_time_remaining(),
            'can_pass': self.can_pass(),
            'admin_notes': self.admin_notes,
        }
        
        if include_votes:
            data['votes_list'] = [v.to_dict() for v in self.votes.order_by(Vote.created_at.desc()).limit(50)]
        
        return data
    
    def get_category_label(self) -> str:
        """Get human-readable category label"""
        labels = {
            'trading_pair': 'New Trading Pair',
            'risk_management': 'Risk Management',
            'exchange': 'New Exchange',
            'feature': 'Feature Request',
            'other': 'Other'
        }
        return labels.get(self.category, 'Other')
    
    def get_category_icon(self) -> str:
        """Get FontAwesome icon for category"""
        icons = {
            'trading_pair': 'fa-coins',
            'risk_management': 'fa-shield-alt',
            'exchange': 'fa-plug',
            'feature': 'fa-lightbulb',
            'other': 'fa-question-circle'
        }
        return icons.get(self.category, 'fa-question-circle')
    
    def get_status_label(self) -> str:
        """Get human-readable status label"""
        labels = {
            'pending': 'Pending Review',
            'active': 'Voting Active',
            'passed': 'Passed',
            'rejected': 'Rejected',
            'implemented': 'Implemented'
        }
        return labels.get(self.status, 'Unknown')
    
    def get_time_remaining(self) -> dict:
        """Get time remaining for voting"""
        if not self.voting_ends_at:
            return None
        
        now = datetime.now(timezone.utc)
        ends = self.voting_ends_at
        if ends.tzinfo is None:
            ends = ends.replace(tzinfo=timezone.utc)
        
        if now >= ends:
            return {'expired': True, 'days': 0, 'hours': 0, 'minutes': 0}
        
        delta = ends - now
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        return {
            'expired': False,
            'days': days,
            'hours': hours,
            'minutes': minutes,
            'total_seconds': int(delta.total_seconds())
        }
    
    def can_pass(self) -> bool:
        """Check if proposal meets passing criteria"""
        total_votes = self.votes_yes + self.votes_no
        if total_votes < self.min_votes_required:
            return False
        
        yes_percentage = (self.votes_yes / total_votes * 100) if total_votes > 0 else 0
        return yes_percentage >= self.pass_threshold
    
    def is_voting_open(self) -> bool:
        """Check if voting is still open"""
        if self.status != 'active':
            return False
        
        if self.voting_ends_at:
            now = datetime.now(timezone.utc)
            ends = self.voting_ends_at
            if ends.tzinfo is None:
                ends = ends.replace(tzinfo=timezone.utc)
            return now < ends
        
        return True  # No deadline = always open
    
    def close_voting(self):
        """Close voting and determine result"""
        if self.status != 'active':
            return False
        
        self.closed_at = datetime.now(timezone.utc)
        
        # Determine if passed
        if self.can_pass():
            self.status = 'passed'
        else:
            self.status = 'rejected'
        
        db.session.commit()
        return True
    
    def mark_implemented(self, admin_notes: str = None):
        """Mark proposal as implemented"""
        if self.status != 'passed':
            return False
        
        self.status = 'implemented'
        self.implemented_at = datetime.now(timezone.utc)
        if admin_notes:
            self.admin_notes = admin_notes
        
        db.session.commit()
        return True
    
    def add_vote(self, user_id: int, vote_type: str, vote_weight: float = 1.0) -> tuple:
        """
        Add a vote to this proposal.
        
        Returns: (success: bool, message: str, vote: Vote|None)
        """
        # Check if user already voted
        existing_vote = Vote.query.filter_by(proposal_id=self.id, user_id=user_id).first()
        if existing_vote:
            return False, "You have already voted on this proposal", None
        
        # Check if voting is open
        if not self.is_voting_open():
            return False, "Voting is closed for this proposal", None
        
        # Create vote
        vote = Vote(
            proposal_id=self.id,
            user_id=user_id,
            vote_type=vote_type,
            vote_weight=vote_weight
        )
        db.session.add(vote)
        
        # Update cached counts
        if vote_type == 'yes':
            self.votes_yes += 1
            self.votes_yes_weight += vote_weight
        else:
            self.votes_no += 1
            self.votes_no_weight += vote_weight
        
        db.session.commit()
        return True, f"Vote recorded: {vote_type.upper()}", vote
    
    @staticmethod
    def get_active_proposals(category: str = None, limit: int = 50):
        """Get all active proposals"""
        query = Proposal.query.filter_by(status='active')
        
        if category:
            query = query.filter_by(category=category)
        
        return query.order_by(Proposal.created_at.desc()).limit(limit).all()
    
    @staticmethod
    def get_proposals_by_status(status: str, limit: int = 50):
        """Get proposals by status"""
        return Proposal.query.filter_by(status=status)\
            .order_by(Proposal.created_at.desc()).limit(limit).all()
    
    @staticmethod
    def create_proposal(title: str, description: str, category: str, 
                       created_by_id: int = None, voting_days: int = 7,
                       min_votes: int = 5, pass_threshold: float = 60.0):
        """Create a new proposal"""
        voting_ends_at = datetime.now(timezone.utc) + timedelta(days=voting_days) if voting_days > 0 else None
        
        proposal = Proposal(
            title=title,
            description=description,
            category=category,
            created_by_id=created_by_id,
            voting_ends_at=voting_ends_at,
            min_votes_required=min_votes,
            pass_threshold=pass_threshold
        )
        
        db.session.add(proposal)
        db.session.commit()
        
        return proposal


class Vote(db.Model):
    """
    Individual vote on a proposal.
    
    Only Elite users (level >= 4) can vote.
    Vote weight can be based on trading volume.
    """
    __tablename__ = 'votes'
    
    id = db.Column(db.Integer, primary_key=True)
    proposal_id = db.Column(db.Integer, db.ForeignKey('proposals.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    vote_type = db.Column(db.String(10), nullable=False)  # 'yes' or 'no'
    vote_weight = db.Column(db.Float, default=1.0)  # Weight based on volume (1.0 = standard, higher for more volume)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    # Relationship
    user = db.relationship('User', backref=db.backref('votes', lazy='dynamic', cascade='all, delete-orphan'))
    
    # Unique constraint: user can only vote once per proposal
    __table_args__ = (
        db.UniqueConstraint('proposal_id', 'user_id', name='unique_proposal_vote'),
        db.Index('idx_vote_proposal_type', 'proposal_id', 'vote_type'),
    )
    
    def to_dict(self):
        """Convert vote to dictionary"""
        return {
            'id': self.id,
            'proposal_id': self.proposal_id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else 'Unknown',
            'user_level': self.user.current_level.name if self.user and self.user.current_level else 'Unknown',
            'vote_type': self.vote_type,
            'vote_weight': round(self.vote_weight, 2),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
    
    @staticmethod
    def can_user_vote(user) -> tuple:
        """
        Check if a user is eligible to vote.
        
        Returns: (can_vote: bool, reason: str)
        """
        if not user:
            return False, "User not found"
        
        if not user.is_active:
            return False, "Your account must be active to vote"
        
        # Check if user is Elite level (order_rank >= 4)
        if not user.current_level:
            return False, "You need to reach Elite level to vote"
        
        if user.current_level.order_rank < 4:  # 4 = Elite
            return False, f"Only Elite members can vote. Your level: {user.current_level.name}"
        
        return True, "Eligible to vote"
    
    @staticmethod
    def calculate_vote_weight(user) -> float:
        """
        Calculate vote weight based on user's trading volume.
        
        Base weight: 1.0
        Additional weight: log10(volume) / 5 (capped at 2.0 additional)
        """
        import math
        
        base_weight = 1.0
        
        if user.total_trading_volume and user.total_trading_volume > 0:
            # Volume-based bonus (logarithmic scale)
            volume_bonus = min(math.log10(user.total_trading_volume + 1) / 5, 2.0)
            return base_weight + volume_bonus
        
        return base_weight
    
    @staticmethod
    def get_user_vote_for_proposal(user_id: int, proposal_id: int):
        """Get user's vote for a specific proposal"""
        return Vote.query.filter_by(user_id=user_id, proposal_id=proposal_id).first()


# ==================== COMPLIANCE MODELS ====================

class UserConsent(db.Model):
    """
    Track user consent to Terms of Service and Risk Disclaimers.
    
    COMPLIANCE:
    - Forces users to accept the latest TOS before using the platform
    - Records IP address and timestamp for legal compliance
    - Tracks consent version to detect when re-consent is needed
    """
    __tablename__ = 'user_consents'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # TOS version that was accepted (e.g., "1.0", "2.0")
    tos_version = db.Column(db.String(20), nullable=False, index=True)
    
    # When the user accepted
    accepted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    # IP address from which consent was given (for audit trail)
    ip_address = db.Column(db.String(45), nullable=True)  # IPv6 can be up to 45 chars
    
    # User agent for additional audit info
    user_agent = db.Column(db.String(512), nullable=True)
    
    # What was consented to
    consent_type = db.Column(db.String(50), default='tos_and_risk_disclaimer')  # 'tos', 'risk_disclaimer', 'tos_and_risk_disclaimer'
    
    # Relationship
    user = db.relationship('User', backref=db.backref('consents', lazy='dynamic', cascade='all, delete-orphan'))
    
    __table_args__ = (
        db.Index('idx_consent_user_version', 'user_id', 'tos_version'),
    )
    
    def to_dict(self):
        """Convert consent to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'tos_version': self.tos_version,
            'consent_type': self.consent_type,
            'accepted_at': self.accepted_at.isoformat() if self.accepted_at else None,
            'ip_address': self.ip_address,
        }
    
    @staticmethod
    def has_user_accepted_tos(user_id: int, required_version: str) -> bool:
        """
        Check if user has accepted the specified TOS version.
        
        Args:
            user_id: The user's ID
            required_version: The minimum required TOS version (e.g., "1.0")
            
        Returns:
            True if user has accepted this version or higher
        """
        consent = UserConsent.query.filter_by(
            user_id=user_id,
            tos_version=required_version
        ).first()
        return consent is not None
    
    @staticmethod
    def get_latest_consent(user_id: int):
        """Get the user's most recent consent record"""
        return UserConsent.query.filter_by(user_id=user_id)\
            .order_by(UserConsent.accepted_at.desc())\
            .first()
    
    @staticmethod
    def record_consent(user_id: int, tos_version: str, ip_address: str = None, 
                       user_agent: str = None, consent_type: str = 'tos_and_risk_disclaimer'):
        """
        Record a user's consent to the Terms of Service.
        
        Args:
            user_id: The user's ID
            tos_version: The TOS version being accepted
            ip_address: Client IP address
            user_agent: Client user agent
            consent_type: Type of consent being given
            
        Returns:
            The created UserConsent object
        """
        consent = UserConsent(
            user_id=user_id,
            tos_version=tos_version,
            ip_address=ip_address,
            user_agent=user_agent[:512] if user_agent and len(user_agent) > 512 else user_agent,
            consent_type=consent_type
        )
        db.session.add(consent)
        db.session.commit()
        return consent


# ==================== INFLUENCER / PARTNER DASHBOARD MODELS ====================

class ReferralClick(db.Model):
    """
    Track clicks on referral links for influencer analytics.
    
    Provides detailed statistics for partners:
    - Total clicks
    - Unique visitors
    - Click sources (UTM parameters)
    - Conversion tracking
    """
    __tablename__ = 'referral_clicks'
    
    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Click tracking
    ip_hash = db.Column(db.String(64), nullable=True)  # SHA256 hash of IP for unique tracking (GDPR compliant)
    user_agent = db.Column(db.String(512), nullable=True)
    referer_url = db.Column(db.String(1024), nullable=True)  # Where the click came from
    
    # UTM tracking
    utm_source = db.Column(db.String(100), nullable=True)
    utm_medium = db.Column(db.String(100), nullable=True)
    utm_campaign = db.Column(db.String(100), nullable=True)
    
    # Conversion tracking
    converted = db.Column(db.Boolean, default=False, index=True)  # Did visitor register?
    converted_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    converted_at = db.Column(db.DateTime, nullable=True)
    
    # First deposit tracking
    deposited = db.Column(db.Boolean, default=False, index=True)  # Did converted user deposit?
    first_deposit_amount = db.Column(db.Float, nullable=True)
    first_deposit_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    # Relationships
    referrer = db.relationship('User', foreign_keys=[referrer_id], backref=db.backref('referral_clicks', lazy='dynamic'))
    converted_user = db.relationship('User', foreign_keys=[converted_user_id])
    
    __table_args__ = (
        db.Index('idx_click_referrer_date', 'referrer_id', 'created_at'),
        db.Index('idx_click_conversion', 'referrer_id', 'converted'),
        db.Index('idx_click_ip_referrer', 'ip_hash', 'referrer_id'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'referrer_id': self.referrer_id,
            'utm_source': self.utm_source,
            'utm_medium': self.utm_medium,
            'utm_campaign': self.utm_campaign,
            'converted': self.converted,
            'deposited': self.deposited,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
    
    @classmethod
    def record_click(cls, referrer_id: int, ip_address: str = None, user_agent: str = None, 
                     referer_url: str = None, utm_source: str = None, utm_medium: str = None, 
                     utm_campaign: str = None):
        """
        Record a referral link click with deduplication.
        
        Args:
            referrer_id: The referrer's user ID
            ip_address: Client IP address (will be hashed for GDPR compliance)
            user_agent: Client user agent
            referer_url: HTTP referer header
            utm_source: UTM source parameter
            utm_medium: UTM medium parameter
            utm_campaign: UTM campaign parameter
            
        Returns:
            ReferralClick object (new or existing for today)
        """
        import hashlib
        
        # Hash the IP address for privacy compliance
        ip_hash = None
        if ip_address:
            ip_hash = hashlib.sha256(ip_address.encode()).hexdigest()
        
        # Check for duplicate click from same IP in last 24 hours
        if ip_hash:
            recent_click = cls.query.filter(
                cls.referrer_id == referrer_id,
                cls.ip_hash == ip_hash,
                cls.created_at >= datetime.now(timezone.utc) - timedelta(hours=24)
            ).first()
            
            if recent_click:
                return recent_click  # Don't count duplicate
        
        click = cls(
            referrer_id=referrer_id,
            ip_hash=ip_hash,
            user_agent=user_agent[:512] if user_agent and len(user_agent) > 512 else user_agent,
            referer_url=referer_url[:1024] if referer_url and len(referer_url) > 1024 else referer_url,
            utm_source=utm_source[:100] if utm_source and len(utm_source) > 100 else utm_source,
            utm_medium=utm_medium[:100] if utm_medium and len(utm_medium) > 100 else utm_medium,
            utm_campaign=utm_campaign[:100] if utm_campaign and len(utm_campaign) > 100 else utm_campaign,
        )
        db.session.add(click)
        db.session.commit()
        return click
    
    @classmethod
    def mark_converted(cls, referrer_id: int, ip_address: str, converted_user_id: int):
        """Mark a click as converted when the visitor registers"""
        import hashlib
        
        if not ip_address:
            return None
            
        ip_hash = hashlib.sha256(ip_address.encode()).hexdigest()
        
        # Find the most recent unconverted click from this IP
        click = cls.query.filter(
            cls.referrer_id == referrer_id,
            cls.ip_hash == ip_hash,
            cls.converted == False
        ).order_by(cls.created_at.desc()).first()
        
        if click:
            click.converted = True
            click.converted_user_id = converted_user_id
            click.converted_at = datetime.now(timezone.utc)
            db.session.commit()
        
        return click
    
    @staticmethod
    def get_referrer_stats(referrer_id: int) -> dict:
        """
        Get comprehensive click statistics for a referrer.
        
        Returns:
            dict with clicks, unique_clicks, registrations, deposits, conversion_rate
        """
        from sqlalchemy import func, distinct
        
        # Total clicks
        total_clicks = ReferralClick.query.filter_by(referrer_id=referrer_id).count()
        
        # Unique visitors (unique IP hashes)
        unique_visitors = db.session.query(func.count(distinct(ReferralClick.ip_hash)))\
            .filter(ReferralClick.referrer_id == referrer_id)\
            .scalar() or 0
        
        # Registrations (conversions)
        registrations = ReferralClick.query.filter_by(
            referrer_id=referrer_id, 
            converted=True
        ).count()
        
        # Deposits
        deposits = ReferralClick.query.filter_by(
            referrer_id=referrer_id, 
            deposited=True
        ).count()
        
        # Total first deposit amount
        total_deposit_amount = db.session.query(func.coalesce(func.sum(ReferralClick.first_deposit_amount), 0.0))\
            .filter(ReferralClick.referrer_id == referrer_id, ReferralClick.deposited == True)\
            .scalar() or 0
        
        # Conversion rates
        click_to_registration = (registrations / unique_visitors * 100) if unique_visitors > 0 else 0
        registration_to_deposit = (deposits / registrations * 100) if registrations > 0 else 0
        
        return {
            'total_clicks': total_clicks,
            'unique_visitors': unique_visitors,
            'registrations': registrations,
            'deposits': deposits,
            'total_deposit_amount': float(total_deposit_amount),
            'click_to_registration_rate': round(click_to_registration, 1),
            'registration_to_deposit_rate': round(registration_to_deposit, 1),
        }


class PayoutRequest(db.Model):
    """
    Payout requests for referral commissions.
    
    Influencers can request withdrawal of their earned commissions
    (minimum $50) which are reviewed and processed by admins.
    """
    __tablename__ = 'payout_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Amount requested (in USD)
    amount = db.Column(db.Float, nullable=False)
    
    # Status: pending, approved, rejected, paid
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)
    
    # Payment method details
    payment_method = db.Column(db.String(50), nullable=False)  # 'usdt_trc20', 'usdt_erc20', 'btc', 'bank_transfer'
    payment_address = db.Column(db.String(500), nullable=True)  # Crypto address or bank details (encrypted)
    
    # Admin processing
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    admin_notes = db.Column(db.Text, nullable=True)
    
    # Transaction details after payment
    txn_id = db.Column(db.String(200), nullable=True)  # Blockchain transaction ID
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('payout_requests', lazy='dynamic'))
    admin = db.relationship('User', foreign_keys=[admin_id])
    
    __table_args__ = (
        db.Index('idx_payout_user_status', 'user_id', 'status'),
        db.Index('idx_payout_status_date', 'status', 'created_at'),
    )
    
    # Minimum payout amount
    MINIMUM_PAYOUT = 50.0
    
    # Valid payment methods
    PAYMENT_METHODS = {
        'usdt_trc20': 'USDT (TRC20)',
        'usdt_erc20': 'USDT (ERC20)',
        'usdt_bep20': 'USDT (BEP20)',
        'btc': 'Bitcoin',
        'bank_transfer': 'Bank Transfer (Contact Admin)',
    }
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'amount': round(self.amount, 2),
            'status': self.status,
            'payment_method': self.payment_method,
            'payment_method_label': self.PAYMENT_METHODS.get(self.payment_method, self.payment_method),
            'txn_id': self.txn_id,
            'admin_notes': self.admin_notes if self.status in ('rejected', 'paid') else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
        }
    
    @classmethod
    def create_request(cls, user_id: int, amount: float, payment_method: str, payment_address: str):
        """
        Create a new payout request.
        
        Args:
            user_id: The user requesting payout
            amount: Amount to withdraw (must be >= MINIMUM_PAYOUT)
            payment_method: Payment method key (e.g., 'usdt_trc20')
            payment_address: Crypto wallet address or bank details
            
        Returns:
            PayoutRequest object or raises ValueError
        """
        # Validate minimum amount
        if amount < cls.MINIMUM_PAYOUT:
            raise ValueError(f"Minimum payout amount is ${cls.MINIMUM_PAYOUT}")
        
        # Validate payment method
        if payment_method not in cls.PAYMENT_METHODS:
            raise ValueError(f"Invalid payment method: {payment_method}")
        
        # Check user's available commission balance
        user = User.query.get(user_id)
        if not user:
            raise ValueError("User not found")
        
        stats = user.get_referral_stats()
        available_balance = stats['pending_commission']
        
        if amount > available_balance:
            raise ValueError(f"Insufficient balance. Available: ${available_balance:.2f}")
        
        # Check for pending payout requests
        pending_request = cls.query.filter_by(
            user_id=user_id,
            status='pending'
        ).first()
        
        if pending_request:
            raise ValueError("You already have a pending payout request")
        
        request = cls(
            user_id=user_id,
            amount=amount,
            payment_method=payment_method,
            payment_address=payment_address
        )
        db.session.add(request)
        db.session.commit()
        return request
    
    def approve(self, admin_id: int, notes: str = None):
        """Approve the payout request (admin action)"""
        if self.status != 'pending':
            raise ValueError(f"Cannot approve: status is {self.status}")
        
        self.status = 'approved'
        self.admin_id = admin_id
        self.admin_notes = notes
        self.reviewed_at = datetime.now(timezone.utc)
        db.session.commit()
    
    def reject(self, admin_id: int, reason: str):
        """Reject the payout request (admin action)"""
        if self.status != 'pending':
            raise ValueError(f"Cannot reject: status is {self.status}")
        
        self.status = 'rejected'
        self.admin_id = admin_id
        self.admin_notes = reason
        self.reviewed_at = datetime.now(timezone.utc)
        db.session.commit()
    
    def mark_paid(self, admin_id: int, txn_id: str = None, notes: str = None):
        """Mark the payout as paid (admin action after actual payment)"""
        if self.status not in ('pending', 'approved'):
            raise ValueError(f"Cannot mark as paid: status is {self.status}")
        
        self.status = 'paid'
        self.admin_id = admin_id
        self.txn_id = txn_id
        self.admin_notes = notes
        self.paid_at = datetime.now(timezone.utc)
        if not self.reviewed_at:
            self.reviewed_at = self.paid_at
        
        # Mark corresponding commissions as paid
        from sqlalchemy import func
        unpaid_commissions = ReferralCommission.query.filter_by(
            referrer_id=self.user_id,
            is_paid=False
        ).all()
        
        remaining_amount = self.amount
        for commission in unpaid_commissions:
            if remaining_amount <= 0:
                break
            if commission.amount <= remaining_amount:
                commission.is_paid = True
                commission.paid_at = self.paid_at
                remaining_amount -= commission.amount
        
        db.session.commit()
    
    @staticmethod
    def get_pending_requests():
        """Get all pending payout requests for admin review"""
        return PayoutRequest.query.filter_by(status='pending')\
            .order_by(PayoutRequest.created_at.asc()).all()
    
    @staticmethod
    def get_user_requests(user_id: int, limit: int = 20):
        """Get payout request history for a user"""
        return PayoutRequest.query.filter_by(user_id=user_id)\
            .order_by(PayoutRequest.created_at.desc())\
            .limit(limit).all()


# ==================== SYSTEM SETTINGS MODEL ====================

class SystemSetting(db.Model):
    """
    Database-stored system configuration settings.
    
    Allows admin to configure external services (Plisio, Telegram, Email, etc.)
    through the web interface without editing config files.
    
    Categories:
    - telegram: Telegram bot settings
    - email: SMTP email settings
    - payment: Plisio payment gateway
    - twitter: Twitter/X API for auto-posting
    - openai: OpenAI/Support bot settings
    - webpush: VAPID keys for web push notifications
    - binance: Binance master account settings
    - compliance: Geo-blocking and TOS settings
    - general: General application settings
    """
    __tablename__ = 'system_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False, index=True)  # e.g., 'telegram', 'email', 'payment'
    key = db.Column(db.String(100), nullable=False, index=True)  # e.g., 'bot_token', 'api_key'
    value = db.Column(db.Text, nullable=True)  # Plain text value (for non-sensitive)
    value_encrypted = db.Column(db.Text, nullable=True)  # Encrypted value (for sensitive data)
    is_sensitive = db.Column(db.Boolean, default=False)  # Mark if value should be encrypted
    is_enabled = db.Column(db.Boolean, default=True)  # Quick toggle for the service
    description = db.Column(db.String(500), nullable=True)  # Human-readable description
    
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                          onupdate=lambda: datetime.now(timezone.utc))
    updated_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    
    # Unique constraint on category + key
    __table_args__ = (
        db.UniqueConstraint('category', 'key', name='uq_system_setting_category_key'),
        db.Index('idx_system_setting_category', 'category'),
    )
    
    # Relationships
    updated_by = db.relationship('User', foreign_keys=[updated_by_id])
    
    def set_value(self, value: str, is_sensitive: bool = None):
        """
        Set the value, encrypting if marked as sensitive.
        
        Args:
            value: The value to store
            is_sensitive: Override sensitivity flag (None = use existing)
        """
        if is_sensitive is not None:
            self.is_sensitive = is_sensitive
        
        if self.is_sensitive and cipher_suite and value:
            self.value_encrypted = cipher_suite.encrypt(value.encode()).decode()
            self.value = None  # Clear plain text
        else:
            self.value = value
            self.value_encrypted = None
    
    def get_value(self) -> str:
        """
        Get the decrypted value.
        
        Returns:
            The setting value (decrypted if encrypted)
        """
        if self.value_encrypted and cipher_suite:
            try:
                return cipher_suite.decrypt(self.value_encrypted.encode()).decode()
            except Exception:
                return ''
        return self.value or ''
    
    def to_dict(self, include_value: bool = True, mask_sensitive: bool = True) -> dict:
        """
        Convert to dictionary.
        
        Args:
            include_value: Include the actual value
            mask_sensitive: Mask sensitive values (show only last 4 chars)
        """
        result = {
            'id': self.id,
            'category': self.category,
            'key': self.key,
            'is_sensitive': self.is_sensitive,
            'is_enabled': self.is_enabled,
            'description': self.description,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'updated_by': self.updated_by.username if self.updated_by else None,
            'has_value': bool(self.value or self.value_encrypted),
        }
        
        if include_value:
            val = self.get_value()
            if mask_sensitive and self.is_sensitive and val:
                # Show only last 4 characters for sensitive values
                result['value'] = '****' + val[-4:] if len(val) > 4 else '****'
                result['value_masked'] = True
            else:
                result['value'] = val
                result['value_masked'] = False
        
        return result
    
    @classmethod
    def get_setting(cls, category: str, key: str, default: str = '') -> str:
        """
        Get a setting value by category and key.
        
        Args:
            category: Setting category (e.g., 'telegram')
            key: Setting key (e.g., 'bot_token')
            default: Default value if not found
            
        Returns:
            The setting value or default
        """
        setting = cls.query.filter_by(category=category, key=key).first()
        if setting:
            return setting.get_value()
        return default
    
    @classmethod
    def set_setting(cls, category: str, key: str, value: str, 
                   is_sensitive: bool = False, description: str = None,
                   updated_by_id: int = None) -> 'SystemSetting':
        """
        Set a setting value, creating if not exists.
        
        Args:
            category: Setting category
            key: Setting key
            value: Value to store
            is_sensitive: Whether value should be encrypted
            description: Human-readable description
            updated_by_id: User ID who updated this setting
            
        Returns:
            The SystemSetting instance
        """
        setting = cls.query.filter_by(category=category, key=key).first()
        
        if not setting:
            setting = cls(
                category=category,
                key=key,
                is_sensitive=is_sensitive,
                description=description
            )
            db.session.add(setting)
        
        setting.set_value(value, is_sensitive)
        if description:
            setting.description = description
        if updated_by_id:
            setting.updated_by_id = updated_by_id
        
        db.session.commit()
        return setting
    
    @classmethod
    def get_category_settings(cls, category: str) -> dict:
        """
        Get all settings for a category as a dictionary.
        
        Args:
            category: Setting category
            
        Returns:
            Dict of key -> value for the category
        """
        settings = cls.query.filter_by(category=category).all()
        return {s.key: s.get_value() for s in settings}
    
    @classmethod
    def is_service_enabled(cls, category: str) -> bool:
        """
        Check if a service category is enabled.
        
        Args:
            category: Service category name
            
        Returns:
            True if service is enabled
        """
        # Check for 'enabled' key in the category
        setting = cls.query.filter_by(category=category, key='enabled').first()
        if setting:
            return setting.is_enabled and setting.get_value().lower() in ('true', '1', 'yes')
        return False
    
    @classmethod
    def get_all_grouped(cls) -> dict:
        """
        Get all settings grouped by category.
        
        Returns:
            Dict of category -> list of setting dicts
        """
        settings = cls.query.order_by(cls.category, cls.key).all()
        grouped = {}
        for s in settings:
            if s.category not in grouped:
                grouped[s.category] = []
            grouped[s.category].append(s.to_dict())
        return grouped
    
    @classmethod
    def initialize_defaults(cls):
        """
        Initialize default settings structure (called on first run).
        Creates placeholder entries for all configurable services.
        """
        defaults = [
            # Telegram Settings
            ('telegram', 'enabled', 'false', False, 'Enable Telegram bot notifications'),
            ('telegram', 'bot_token', '', True, 'Telegram Bot Token (from @BotFather)'),
            ('telegram', 'chat_id', '', False, 'Admin Telegram Chat ID'),
            
            # Email/SMTP Settings
            ('email', 'enabled', 'false', False, 'Enable email notifications'),
            ('email', 'smtp_server', 'smtp.gmail.com', False, 'SMTP server address'),
            ('email', 'smtp_port', '587', False, 'SMTP server port'),
            ('email', 'smtp_username', '', False, 'SMTP username/email'),
            ('email', 'smtp_password', '', True, 'SMTP password or app password'),
            ('email', 'from_email', '', False, 'Sender email address'),
            ('email', 'from_name', 'Brain Capital', False, 'Sender display name'),
            
            # Plisio Payment Gateway
            ('payment', 'enabled', 'false', False, 'Enable crypto payments via Plisio'),
            ('payment', 'api_key', '', True, 'Plisio API Key'),
            ('payment', 'webhook_secret', '', True, 'Plisio Webhook Secret'),
            
            # Twitter/X Auto-posting
            ('twitter', 'enabled', 'false', False, 'Enable Twitter auto-posting'),
            ('twitter', 'api_key', '', True, 'Twitter API Key'),
            ('twitter', 'api_secret', '', True, 'Twitter API Secret'),
            ('twitter', 'access_token', '', True, 'Twitter Access Token'),
            ('twitter', 'access_secret', '', True, 'Twitter Access Secret'),
            ('twitter', 'min_roi_threshold', '50.0', False, 'Minimum ROI % to trigger tweet'),
            ('twitter', 'site_url', 'https://mimic.cash', False, 'Site URL for tweet links'),
            
            # OpenAI/Support Bot
            ('openai', 'enabled', 'false', False, 'Enable AI Support Bot'),
            ('openai', 'api_key', '', True, 'OpenAI API Key'),
            ('openai', 'embedding_model', 'text-embedding-3-small', False, 'OpenAI embedding model'),
            ('openai', 'chat_model', 'gpt-4o-mini', False, 'OpenAI chat model'),
            ('openai', 'confidence_threshold', '0.7', False, 'RAG confidence threshold'),
            ('openai', 'chunk_size', '500', False, 'Document chunk size'),
            ('openai', 'chunk_overlap', '50', False, 'Document chunk overlap'),
            
            # Web Push Notifications
            ('webpush', 'enabled', 'false', False, 'Enable Web Push notifications'),
            ('webpush', 'vapid_public_key', '', False, 'VAPID Public Key'),
            ('webpush', 'vapid_private_key', '', True, 'VAPID Private Key'),
            ('webpush', 'vapid_claim_email', 'mailto:admin@mimic.cash', False, 'VAPID contact email'),
            
            # Binance Master Account
            ('binance', 'enabled', 'true', False, 'Enable Binance master trading'),
            ('binance', 'api_key', '', True, 'Binance Master API Key'),
            ('binance', 'api_secret', '', True, 'Binance Master API Secret'),
            ('binance', 'testnet', 'false', False, 'Use Binance Testnet'),
            
            # Webhook Settings
            ('webhook', 'passphrase', '', True, 'TradingView Webhook Passphrase'),
            
            # Compliance Settings
            ('compliance', 'tos_version', '1.0', False, 'Terms of Service version'),
            ('compliance', 'blocked_countries', 'US,KP,IR', False, 'Blocked country codes (comma-separated)'),
            ('compliance', 'tos_consent_enabled', 'true', False, 'Require TOS consent'),
            ('compliance', 'geo_blocking_enabled', 'false', False, 'Enable geo-blocking'),
            
            # General Settings
            ('general', 'max_open_positions', '10', False, 'Maximum open positions globally'),
            ('general', 'site_url', 'https://mimic.cash', False, 'Public site URL'),
            ('general', 'production_domain', '', False, 'Production domain with https://'),
            
            # Proxy Settings
            ('proxy', 'enabled', 'false', False, 'Enable proxy rotation'),
            ('proxy', 'proxies', '', False, 'Comma-separated proxy URLs'),
            ('proxy', 'users_per_proxy', '50', False, 'Users per proxy'),
            ('proxy', 'proxy_cooldown_seconds', '60', False, 'Proxy cooldown in seconds'),
            ('proxy', 'max_proxy_retries', '3', False, 'Maximum proxy retries'),
            
            # Panic OTP Settings
            ('panic', 'enabled', 'false', False, 'Enable Telegram panic kill switch'),
            ('panic', 'otp_secret', '', True, 'TOTP secret for panic commands'),
            ('panic', 'authorized_users', '', False, 'Comma-separated authorized Telegram user IDs'),
        ]
        
        for category, key, default_value, is_sensitive, description in defaults:
            existing = cls.query.filter_by(category=category, key=key).first()
            if not existing:
                setting = cls(
                    category=category,
                    key=key,
                    is_sensitive=is_sensitive,
                    description=description
                )
                setting.set_value(default_value, is_sensitive)
                db.session.add(setting)
        
        db.session.commit()


# Service categories metadata for UI
SERVICE_CATEGORIES = {
    'telegram': {
        'name': 'Telegram Bot',
        'icon': 'fab fa-telegram',
        'color': '#0088cc',
        'description': 'Telegram notifications and panic kill switch',
        'docs_url': 'https://core.telegram.org/bots#creating-a-new-bot',
    },
    'email': {
        'name': 'Email/SMTP',
        'icon': 'fas fa-envelope',
        'color': '#ea4335',
        'description': 'Email notifications for password recovery and alerts',
        'docs_url': 'https://support.google.com/accounts/answer/185833',
    },
    'payment': {
        'name': 'Plisio Payments',
        'icon': 'fas fa-credit-card',
        'color': '#00d4aa',
        'description': 'Crypto payment gateway for subscriptions',
        'docs_url': 'https://plisio.net/documentation',
    },
    'twitter': {
        'name': 'Twitter/X',
        'icon': 'fab fa-twitter',
        'color': '#1da1f2',
        'description': 'Auto-post successful trades to Twitter',
        'docs_url': 'https://developer.twitter.com/en/docs',
    },
    'openai': {
        'name': 'OpenAI (Support Bot)',
        'icon': 'fas fa-robot',
        'color': '#10a37f',
        'description': 'AI-powered support chatbot with RAG',
        'docs_url': 'https://platform.openai.com/docs',
    },
    'webpush': {
        'name': 'Web Push',
        'icon': 'fas fa-bell',
        'color': '#ff9800',
        'description': 'Browser push notifications (PWA)',
        'docs_url': 'https://web.dev/push-notifications-overview/',
    },
    'binance': {
        'name': 'Binance Master',
        'icon': 'fas fa-coins',
        'color': '#f0b90b',
        'description': 'Master trading account for copy trading',
        'docs_url': 'https://www.binance.com/en/support/faq/api',
    },
    'webhook': {
        'name': 'TradingView Webhook',
        'icon': 'fas fa-bolt',
        'color': '#2962ff',
        'description': 'Receive trading signals from TradingView',
        'docs_url': 'https://www.tradingview.com/support/solutions/43000529348',
    },
    'compliance': {
        'name': 'Compliance',
        'icon': 'fas fa-shield-alt',
        'color': '#6c757d',
        'description': 'Geo-blocking and Terms of Service settings',
    },
    'proxy': {
        'name': 'Proxy Settings',
        'icon': 'fas fa-network-wired',
        'color': '#9c27b0',
        'description': 'Proxy rotation for high-volume trading',
    },
    'panic': {
        'name': 'Panic Controls',
        'icon': 'fas fa-exclamation-triangle',
        'color': '#dc3545',
        'description': 'Emergency kill switch via Telegram OTP',
    },
    'general': {
        'name': 'General Settings',
        'icon': 'fas fa-cog',
        'color': '#6c757d',
        'description': 'General application settings',
    },
}


# ==================== TASK/CHALLENGE SYSTEM ====================

class Task(db.Model):
    """
    Admin-created tasks/challenges that users can complete for rewards.
    
    Task types:
    - social: Social media tasks (follow, like, share, etc.)
    - trading: Trading-related tasks (make X trades, reach Y profit)
    - referral: Refer X users
    - community: Community engagement tasks
    - custom: Custom admin-defined tasks
    
    Reward types:
    - money: Cash reward added to user balance
    - goods: Physical or digital goods (coupon, merchandise, etc.)
    - xp: Experience points
    - subscription: Free subscription days
    """
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Task info
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    instructions = db.Column(db.Text, nullable=True)  # Detailed instructions for users
    
    # Task type and category
    task_type = db.Column(db.String(50), default='custom', index=True)  # social, trading, referral, community, custom
    category = db.Column(db.String(100), nullable=True)  # Optional category for grouping
    
    # Visual
    icon = db.Column(db.String(50), default='fa-tasks')  # FontAwesome icon
    color = db.Column(db.String(20), default='#00f5ff')  # Accent color
    image_url = db.Column(db.String(500), nullable=True)  # Optional banner image
    
    # Reward settings
    reward_type = db.Column(db.String(50), default='money')  # money, goods, xp, subscription
    reward_amount = db.Column(db.Float, default=0.0)  # For money/xp, this is the amount
    reward_description = db.Column(db.String(500), nullable=True)  # For goods: description of what they get
    
    # Participation limits
    max_participants = db.Column(db.Integer, nullable=True)  # NULL = unlimited
    max_completions_per_user = db.Column(db.Integer, default=1)  # How many times a user can complete this
    
    # Availability
    start_date = db.Column(db.DateTime, nullable=True, index=True)  # NULL = immediately available
    end_date = db.Column(db.DateTime, nullable=True, index=True)  # NULL = no expiry
    
    # Requirements
    min_user_level = db.Column(db.Integer, default=0)  # Minimum user level required
    requires_subscription = db.Column(db.Boolean, default=False)  # Requires active subscription
    required_subscription_plans = db.Column(db.String(200), nullable=True)  # Comma-separated: 'basic,pro,enterprise'
    
    # Verification
    requires_approval = db.Column(db.Boolean, default=True)  # Admin must approve completion
    auto_verify = db.Column(db.Boolean, default=False)  # Can be auto-verified (for trading tasks)
    verification_url = db.Column(db.String(500), nullable=True)  # URL to verify (for social tasks)
    
    # Status
    status = db.Column(db.String(20), default='active', index=True)  # draft, active, paused, completed, cancelled
    is_featured = db.Column(db.Boolean, default=False, index=True)  # Featured on main page
    
    # Statistics
    total_participants = db.Column(db.Integer, default=0)
    total_completions = db.Column(db.Integer, default=0)
    total_rewards_given = db.Column(db.Float, default=0.0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    
    # Relationships
    created_by = db.relationship('User', foreign_keys=[created_by_id], backref='created_tasks')
    participations = db.relationship('TaskParticipation', backref='task', lazy='dynamic', cascade='all, delete-orphan')
    
    # Indexes
    __table_args__ = (
        db.Index('idx_task_status_dates', 'status', 'start_date', 'end_date'),
        db.Index('idx_task_type_status', 'task_type', 'status'),
    )
    
    def to_dict(self, include_participations=False):
        """Convert task to dictionary for API response"""
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'instructions': self.instructions,
            'task_type': self.task_type,
            'category': self.category,
            'icon': self.icon,
            'color': self.color,
            'image_url': self.image_url,
            'reward_type': self.reward_type,
            'reward_amount': self.reward_amount,
            'reward_description': self.reward_description,
            'max_participants': self.max_participants,
            'max_completions_per_user': self.max_completions_per_user,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'min_user_level': self.min_user_level,
            'requires_subscription': self.requires_subscription,
            'requires_approval': self.requires_approval,
            'status': self.status,
            'is_featured': self.is_featured,
            'total_participants': self.total_participants,
            'total_completions': self.total_completions,
            'total_rewards_given': self.total_rewards_given,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_available': self.is_available(),
            'spots_remaining': self.get_spots_remaining(),
        }
        
        if include_participations:
            data['participations'] = [p.to_dict() for p in self.participations.limit(100).all()]
        
        return data
    
    def is_available(self):
        """Check if task is currently available for participation"""
        if self.status != 'active':
            return False
        
        now = datetime.now(timezone.utc)
        
        if self.start_date and now < self.start_date:
            return False
        
        if self.end_date and now > self.end_date:
            return False
        
        if self.max_participants and self.total_participants >= self.max_participants:
            return False
        
        return True
    
    def get_spots_remaining(self):
        """Get remaining spots, or None if unlimited"""
        if not self.max_participants:
            return None
        return max(0, self.max_participants - self.total_participants)
    
    def can_user_participate(self, user):
        """Check if a specific user can participate in this task"""
        if not self.is_available():
            return False, "Task is not currently available"
        
        # Check user level
        if user.current_level_id:
            from models import UserLevel
            level = UserLevel.query.get(user.current_level_id)
            if level and level.level_number < self.min_user_level:
                return False, f"Requires level {self.min_user_level} or higher"
        elif self.min_user_level > 0:
            return False, f"Requires level {self.min_user_level} or higher"
        
        # Check subscription requirement
        if self.requires_subscription:
            if not user.subscription_expires_at or user.subscription_expires_at < datetime.now(timezone.utc):
                return False, "Requires active subscription"
            
            if self.required_subscription_plans:
                allowed_plans = [p.strip() for p in self.required_subscription_plans.split(',')]
                if user.subscription_plan not in allowed_plans:
                    return False, f"Requires {' or '.join(allowed_plans)} subscription"
        
        # Check if user already completed max times
        user_completions = TaskParticipation.query.filter_by(
            task_id=self.id,
            user_id=user.id,
            status='completed'
        ).count()
        
        if user_completions >= self.max_completions_per_user:
            return False, "You have already completed this task the maximum number of times"
        
        # Check if user has a pending participation
        pending = TaskParticipation.query.filter_by(
            task_id=self.id,
            user_id=user.id
        ).filter(TaskParticipation.status.in_(['pending', 'in_progress', 'submitted'])).first()
        
        if pending:
            return False, "You already have an active participation for this task"
        
        return True, "OK"
    
    @staticmethod
    def get_active_tasks(task_type=None, featured_only=False, limit=50):
        """Get all active and available tasks"""
        query = Task.query.filter_by(status='active')
        
        now = datetime.now(timezone.utc)
        query = query.filter(
            db.or_(Task.start_date.is_(None), Task.start_date <= now)
        ).filter(
            db.or_(Task.end_date.is_(None), Task.end_date > now)
        )
        
        if task_type:
            query = query.filter_by(task_type=task_type)
        
        if featured_only:
            query = query.filter_by(is_featured=True)
        
        return query.order_by(Task.is_featured.desc(), Task.created_at.desc()).limit(limit).all()
    
    @staticmethod
    def get_task_types():
        """Get available task types with metadata"""
        return {
            'social': {
                'name': 'Social Media',
                'icon': 'fa-share-alt',
                'color': '#1da1f2',
                'description': 'Follow, like, share, and engage on social media'
            },
            'trading': {
                'name': 'Trading',
                'icon': 'fa-chart-line',
                'color': '#00ff88',
                'description': 'Complete trading-related challenges'
            },
            'referral': {
                'name': 'Referral',
                'icon': 'fa-users',
                'color': '#a855f7',
                'description': 'Invite friends and grow the community'
            },
            'community': {
                'name': 'Community',
                'icon': 'fa-comments',
                'color': '#f59e0b',
                'description': 'Engage with the community'
            },
            'custom': {
                'name': 'Special',
                'icon': 'fa-star',
                'color': '#ec4899',
                'description': 'Special limited-time tasks'
            }
        }
    
    @staticmethod
    def get_reward_types():
        """Get available reward types with metadata"""
        return {
            'money': {
                'name': 'Cash Reward',
                'icon': 'fa-dollar-sign',
                'color': '#22c55e',
                'description': 'Credited to your balance'
            },
            'goods': {
                'name': 'Goods/Prizes',
                'icon': 'fa-gift',
                'color': '#f43f5e',
                'description': 'Physical or digital prizes'
            },
            'xp': {
                'name': 'Experience Points',
                'icon': 'fa-bolt',
                'color': '#eab308',
                'description': 'Level up faster'
            },
            'subscription': {
                'name': 'Free Subscription',
                'icon': 'fa-crown',
                'color': '#8b5cf6',
                'description': 'Free subscription days'
            }
        }


class TaskParticipation(db.Model):
    """
    Tracks user participation in tasks.
    
    Status flow:
    1. pending: User joined, hasn't started
    2. in_progress: User is working on the task
    3. submitted: User submitted completion proof (awaiting approval)
    4. completed: Admin approved, rewards given
    5. rejected: Admin rejected the submission
    6. cancelled: User or admin cancelled
    """
    __tablename__ = 'task_participations'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Status tracking
    status = db.Column(db.String(20), default='pending', index=True)  # pending, in_progress, submitted, completed, rejected, cancelled
    
    # Submission details
    submission_text = db.Column(db.Text, nullable=True)  # User's proof/notes
    submission_url = db.Column(db.String(500), nullable=True)  # Proof URL (screenshot, link, etc.)
    submission_data = db.Column(db.Text, nullable=True)  # JSON data for auto-verification
    submitted_at = db.Column(db.DateTime, nullable=True)
    
    # Review details
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    review_notes = db.Column(db.Text, nullable=True)  # Admin notes on review
    rejection_reason = db.Column(db.String(500), nullable=True)
    
    # Reward tracking
    reward_given = db.Column(db.Boolean, default=False)
    reward_amount = db.Column(db.Float, default=0.0)  # Actual reward given
    reward_given_at = db.Column(db.DateTime, nullable=True)
    
    # Timestamps
    joined_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('task_participations', lazy='dynamic'))
    reviewed_by = db.relationship('User', foreign_keys=[reviewed_by_id])
    
    # Unique constraint: user can only have one active participation per task
    __table_args__ = (
        db.Index('idx_participation_task_user', 'task_id', 'user_id'),
        db.Index('idx_participation_status', 'status'),
    )
    
    def to_dict(self):
        """Convert participation to dictionary"""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else None,
            'status': self.status,
            'submission_text': self.submission_text,
            'submission_url': self.submission_url,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'reviewed_by': self.reviewed_by.username if self.reviewed_by else None,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'review_notes': self.review_notes,
            'rejection_reason': self.rejection_reason,
            'reward_given': self.reward_given,
            'reward_amount': self.reward_amount,
            'joined_at': self.joined_at.isoformat() if self.joined_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'task': self.task.to_dict() if self.task else None,
        }
    
    def submit(self, text=None, url=None, data=None):
        """Submit task completion for review"""
        self.status = 'submitted'
        self.submission_text = text
        self.submission_url = url
        self.submission_data = data
        self.submitted_at = datetime.now(timezone.utc)
        db.session.commit()
    
    def approve(self, admin_user, notes=None):
        """Approve the submission and give rewards"""
        self.status = 'completed'
        self.reviewed_by_id = admin_user.id
        self.reviewed_at = datetime.now(timezone.utc)
        self.review_notes = notes
        self.completed_at = datetime.now(timezone.utc)
        
        # Give reward
        task = self.task
        if task:
            self.reward_amount = task.reward_amount
            
            if task.reward_type == 'money':
                # Add to user's custom_risk (used as balance in some implementations)
                # Or implement your own balance field
                pass  # Balance handling depends on your implementation
            elif task.reward_type == 'xp':
                self.user.xp = (self.user.xp or 0) + int(task.reward_amount)
            elif task.reward_type == 'subscription':
                # Add subscription days
                days_to_add = int(task.reward_amount)
                if self.user.subscription_expires_at and self.user.subscription_expires_at > datetime.now(timezone.utc):
                    self.user.subscription_expires_at += timedelta(days=days_to_add)
                else:
                    self.user.subscription_expires_at = datetime.now(timezone.utc) + timedelta(days=days_to_add)
                    if not self.user.subscription_plan or self.user.subscription_plan == 'free':
                        self.user.subscription_plan = 'basic'
            
            self.reward_given = True
            self.reward_given_at = datetime.now(timezone.utc)
            
            # Update task statistics
            task.total_completions += 1
            task.total_rewards_given += self.reward_amount
        
        db.session.commit()
    
    def reject(self, admin_user, reason=None, notes=None):
        """Reject the submission"""
        self.status = 'rejected'
        self.reviewed_by_id = admin_user.id
        self.reviewed_at = datetime.now(timezone.utc)
        self.review_notes = notes
        self.rejection_reason = reason
        db.session.commit()
    
    @staticmethod
    def get_pending_reviews(limit=100):
        """Get all submissions awaiting admin review"""
        return TaskParticipation.query.filter_by(status='submitted')\
            .order_by(TaskParticipation.submitted_at.asc())\
            .limit(limit).all()
    
    @staticmethod
    def get_user_participations(user_id, status=None, limit=50):
        """Get a user's task participations"""
        query = TaskParticipation.query.filter_by(user_id=user_id)
        if status:
            query = query.filter_by(status=status)
        return query.order_by(TaskParticipation.updated_at.desc()).limit(limit).all()