"""
Pydantic Schemas for Exchange Management API
Request/Response validation for FastAPI endpoints
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from enum import Enum
from datetime import datetime


class ExchangeStatus(str, Enum):
    """Exchange approval status"""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SupportedExchange(str, Enum):
    """
    Supported exchange names - Top 20 by CoinMarketCap trading volume
    """
    # Tier 1 - Major exchanges
    BINANCE = "binance"
    COINBASE = "coinbase"
    BYBIT = "bybit"
    OKX = "okx"
    UPBIT = "upbit"
    
    # Tier 2 - Large exchanges
    BITGET = "bitget"
    GATE = "gate"
    KUCOIN = "kucoin"
    KRAKEN = "kraken"
    HTX = "htx"
    
    # Tier 3 - Mid-size exchanges
    MEXC = "mexc"
    CRYPTOCOM = "cryptocom"
    BITSTAMP = "bitstamp"
    BITFINEX = "bitfinex"
    BITHUMB = "bithumb"
    
    # Tier 4 - Additional exchanges
    WHITEBIT = "whitebit"
    LBANK = "lbank"
    POLONIEX = "poloniex"
    GEMINI = "gemini"
    BITMART = "bitmart"
    
    # Tier 5 - More exchanges
    XT = "xt"
    BINGX = "bingx"
    PHEMEX = "phemex"
    TOOBIT = "toobit"
    KCEX = "kcex"
    WEEX = "weex"
    BITUNIX = "bitunix"
    OURBIT = "ourbit"
    COFINEX = "cofinex"


# ==================== USER SCHEMAS ====================

class ExchangeCreateRequest(BaseModel):
    """Request schema for adding a new exchange"""
    exchange_name: SupportedExchange = Field(..., description="Exchange name (binance, bybit, okx, etc.)")
    api_key: str = Field(..., min_length=16, max_length=200, description="API Key")
    api_secret: str = Field(..., min_length=16, max_length=200, description="API Secret")
    passphrase: Optional[str] = Field(None, max_length=200, description="Passphrase (required for OKX/KuCoin)")
    label: str = Field(..., min_length=1, max_length=100, description="User's custom label for this exchange")
    
    @field_validator('api_key', 'api_secret')
    @classmethod
    def validate_api_credentials(cls, v: str) -> str:
        """
        Validate API credentials format
        
        SECURITY: Validates alphanumeric format, prevents injection attacks
        """
        import re
        
        if not v or len(v.strip()) < 16:
            raise ValueError("API credentials must be at least 16 characters")
        
        v = v.strip()
        
        # SECURITY: Only allow alphanumeric characters and common API key chars
        if not re.match(r'^[A-Za-z0-9\-_]+$', v):
            raise ValueError("API credentials contain invalid characters")
        
        # SECURITY: Check for potential injection patterns
        dangerous_patterns = [
            r'<script', r'javascript:', r'SELECT\s+', r'INSERT\s+', 
            r'UPDATE\s+', r'DELETE\s+', r'DROP\s+', r'--', r'/\*'
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("API credentials contain invalid characters")
        
        return v
    
    @field_validator('label')
    @classmethod
    def validate_label(cls, v: str) -> str:
        """Sanitize label to prevent XSS"""
        import html
        v = v.strip()
        # HTML escape to prevent XSS
        v = html.escape(v)
        return v[:100]  # Truncate to max length


class ExchangeResponse(BaseModel):
    """Response schema for exchange listing"""
    id: int
    user_id: int
    exchange_name: str
    label: str
    status: ExchangeStatus
    is_active: bool
    error_message: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class ExchangeToggleRequest(BaseModel):
    """Request schema for toggling exchange active status"""
    is_active: bool = Field(..., description="Enable/disable copying for this exchange")


class ExchangeToggleResponse(BaseModel):
    """Response schema for toggle operation"""
    success: bool
    message: str
    exchange: Optional[ExchangeResponse] = None


# ==================== ADMIN SCHEMAS ====================

class PendingExchangeResponse(BaseModel):
    """Response schema for pending exchange requests"""
    id: int
    user_id: int
    user_username: str
    user_email: Optional[str]
    exchange_name: str
    label: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class ExchangeApproveRequest(BaseModel):
    """Request schema for approving an exchange (optional notification message)"""
    notification_message: Optional[str] = Field(None, max_length=500, description="Optional message to send to user")


class ExchangeRejectRequest(BaseModel):
    """Request schema for rejecting an exchange"""
    reason: str = Field(..., min_length=1, max_length=500, description="Reason for rejection")


class ExchangeApproveResponse(BaseModel):
    """Response schema for approval operation"""
    success: bool
    message: str
    exchange: Optional[ExchangeResponse] = None


class ExchangeRejectResponse(BaseModel):
    """Response schema for rejection operation"""
    success: bool
    message: str


# ==================== PAYMENT SCHEMAS ====================

class SubscriptionPlan(str, Enum):
    """Available subscription plans"""
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"
    BASIC_ANNUAL = "basic_annual"
    PRO_ANNUAL = "pro_annual"


class PaymentStatus(str, Enum):
    """Payment status"""
    PENDING = "pending"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    ERROR = "error"


class PaymentCurrency(str, Enum):
    """Supported crypto currencies for payment"""
    USDT_TRC20 = "USDT_TRC20"
    USDT_ERC20 = "USDT_ERC20"
    BTC = "BTC"
    ETH = "ETH"
    LTC = "LTC"


class PaymentCreateRequest(BaseModel):
    """Request to create a new payment invoice"""
    plan: SubscriptionPlan = Field(..., description="Subscription plan to purchase")
    currency: PaymentCurrency = Field(default=PaymentCurrency.USDT_TRC20, description="Crypto currency for payment")
    
    @field_validator('plan')
    @classmethod
    def validate_plan(cls, v):
        return v


class PaymentCreateResponse(BaseModel):
    """Response with payment invoice details"""
    success: bool
    payment_id: int
    provider_txn_id: str
    invoice_url: str
    wallet_address: str
    amount_usd: float
    amount_crypto: float
    currency: str
    plan: str
    days: int
    expires_at: datetime
    message: str


class PaymentStatusResponse(BaseModel):
    """Response for payment status check"""
    payment_id: int
    status: PaymentStatus
    plan: str
    amount_usd: float
    created_at: datetime
    completed_at: Optional[datetime] = None
    subscription_expires_at: Optional[datetime] = None


class PaymentWebhookData(BaseModel):
    """Plisio webhook payload"""
    txn_id: str
    status: str
    amount: Optional[str] = None
    source_amount: Optional[str] = None
    source_currency: Optional[str] = None
    currency: Optional[str] = None
    order_number: Optional[str] = None
    order_name: Optional[str] = None
    comment: Optional[str] = None
    verify_hash: Optional[str] = None


class SubscriptionStatusResponse(BaseModel):
    """Response for subscription status"""
    is_active: bool
    plan: str
    expires_at: Optional[datetime] = None
    days_remaining: int
    can_trade: bool


# ==================== ERROR SCHEMAS ====================

class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


class ValidationError(BaseModel):
    """Validation error response"""
    error: str = "Validation Error"
    detail: List[str] = Field(default_factory=list)

