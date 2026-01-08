"""
Payment Router - Crypto Payment Gateway Integration (Plisio)
Handles subscription payments via USDT TRC20 and other cryptocurrencies

API Endpoints:
- POST /api/payment/create - Create a new payment invoice
- POST /api/payment/webhook - Handle Plisio webhook callbacks
- GET /api/payment/status/{payment_id} - Check payment status
- GET /api/payment/subscription - Get current subscription status
- GET /api/payment/plans - Get available subscription plans
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import Optional
import logging
import hashlib
import hmac
import httpx
from datetime import datetime, timezone, timedelta

from models import db, User, Payment
from schemas import (
    PaymentCreateRequest,
    PaymentCreateResponse,
    PaymentStatusResponse,
    PaymentWebhookData,
    SubscriptionStatusResponse,
    PaymentStatus,
    SubscriptionPlan,
    ErrorResponse
)
from config import Config
from telegram_notifier import get_notifier

logger = logging.getLogger("PaymentAPI")

# Initialize router
router_payment = APIRouter(prefix="/api/payment", tags=["Payments"])

# Plisio API configuration
PLISIO_API_URL = "https://plisio.net/api/v1"


# ==================== DEPENDENCIES ====================

def get_db():
    """Database session dependency"""
    from app import app
    with app.app_context():
        try:
            yield db.session
        finally:
            db.session.close()


def get_current_user_from_session(request: Request, db_session: Session = Depends(get_db)) -> User:
    """
    Get current user from Flask session cookie
    This allows the payment system to work with the existing Flask auth
    """
    from flask import session
    from app import app
    
    with app.app_context():
        # Try to get user_id from session
        user_id = session.get('user_id') or session.get('_user_id')
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated. Please log in."
            )
        
        user = db_session.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        return user


def get_current_user_from_token(request: Request, db_session: Session = Depends(get_db)) -> User:
    """
    Get current user from Bearer token (same as routers.py)
    """
    import base64
    import time
    
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header"
        )
    
    token = auth_header[7:]  # Remove 'Bearer ' prefix
    TOKEN_MAX_AGE = 3600
    
    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        parts = decoded.split(':')
        if len(parts) != 3:
            raise ValueError("Invalid token format")
        
        user_id_str, timestamp_str, received_signature = parts
        user_id = int(user_id_str)
        timestamp = int(timestamp_str)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format"
        )
    
    # Check expiration
    current_time = int(time.time())
    if current_time - timestamp > TOKEN_MAX_AGE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired"
        )
    
    # Verify signature
    secret_key = Config.SECRET_KEY.encode() if isinstance(Config.SECRET_KEY, str) else Config.SECRET_KEY
    message = f"{user_id}:{timestamp}".encode()
    expected_signature = hmac.new(secret_key, message, hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(received_signature, expected_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token signature"
        )
    
    user = db_session.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return user


# ==================== PLISIO API HELPERS ====================

async def create_plisio_invoice(
    amount: float,
    currency: str,
    order_name: str,
    order_number: str,
    callback_url: str,
    email: str = None
) -> dict:
    """
    Create a payment invoice via Plisio API
    
    Returns dict with:
    - txn_id: Plisio transaction ID
    - invoice_url: URL for user to complete payment
    - wallet: Wallet address for direct payment
    - amount: Amount in crypto
    - expire_utc: Invoice expiration time
    """
    if not Config.PLISIO_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment service not configured"
        )
    
    params = {
        'api_key': Config.PLISIO_API_KEY,
        'source_currency': 'USD',
        'source_amount': str(amount),
        'currency': currency,
        'order_name': order_name,
        'order_number': order_number,
        'callback_url': callback_url,
    }
    
    if email:
        params['email'] = email
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{PLISIO_API_URL}/invoices/new", params=params)
        data = response.json()
        
        if data.get('status') != 'success':
            error_msg = data.get('data', {}).get('message', 'Unknown error')
            logger.error(f"Plisio API error: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Payment provider error: {error_msg}"
            )
        
        return data.get('data', {})


def verify_plisio_webhook(data: dict, verify_hash: str) -> bool:
    """
    Verify Plisio webhook signature
    
    The hash is calculated as: md5(sorted_params + secret_key)
    """
    if not Config.PLISIO_WEBHOOK_SECRET:
        # If no secret configured, skip verification (not recommended for production)
        logger.warning("⚠️ Plisio webhook secret not configured - skipping verification")
        return True
    
    # Build sorted string of parameters
    sorted_params = '&'.join(f"{k}={v}" for k, v in sorted(data.items()) if k != 'verify_hash')
    
    # Calculate expected hash
    to_hash = sorted_params + Config.PLISIO_WEBHOOK_SECRET
    expected_hash = hashlib.md5(to_hash.encode()).hexdigest()
    
    return hmac.compare_digest(expected_hash, verify_hash)


# ==================== ENDPOINTS ====================

@router_payment.get("/plans")
async def get_subscription_plans():
    """
    Get available subscription plans with pricing
    
    Returns list of available plans with prices and features.
    """
    plans = []
    for plan_id, plan_data in Config.SUBSCRIPTION_PLANS.items():
        plans.append({
            'id': plan_id,
            'name': plan_data['name'],
            'price_usd': plan_data['price'],
            'days': plan_data['days'],
            'features': get_plan_features(plan_id)
        })
    
    return {
        'success': True,
        'plans': plans,
        'supported_currencies': ['USDT_TRC20', 'USDT_ERC20', 'BTC', 'ETH', 'LTC']
    }


def get_plan_features(plan_id: str) -> list:
    """Get features for a subscription plan"""
    features = {
        'basic': [
            'Copy trading enabled',
            'Up to 3 exchange connections',
            'Email support',
            'Basic analytics'
        ],
        'pro': [
            'Copy trading enabled',
            'Up to 10 exchange connections',
            'Priority support',
            'Advanced analytics',
            'Custom risk settings',
            'Telegram notifications'
        ],
        'enterprise': [
            'Copy trading enabled',
            'Unlimited exchange connections',
            'Dedicated support',
            'Full analytics suite',
            'API access',
            'White-label options'
        ],
        'basic_annual': [
            'All Basic features',
            '2 months FREE',
            'Priority onboarding'
        ],
        'pro_annual': [
            'All Pro features',
            '2 months FREE',
            'Priority onboarding',
            'Quarterly strategy calls'
        ]
    }
    return features.get(plan_id, [])


@router_payment.post("/create", response_model=PaymentCreateResponse)
async def create_payment(
    request_data: PaymentCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user_from_token),
    db_session: Session = Depends(get_db)
):
    """
    Create a new payment invoice for subscription
    
    1. Validates the selected plan
    2. Creates a Plisio invoice
    3. Stores payment record in database
    4. Returns invoice URL for user to complete payment
    """
    plan_id = request_data.plan.value
    
    if plan_id not in Config.SUBSCRIPTION_PLANS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid subscription plan: {plan_id}"
        )
    
    plan = Config.SUBSCRIPTION_PLANS[plan_id]
    amount_usd = plan['price']
    days = plan['days']
    
    # Generate unique order number
    import secrets
    order_number = f"SUB-{current_user.id}-{secrets.token_hex(8).upper()}"
    
    # Build callback URL for webhook
    # Use the request's base URL or configured domain
    base_url = str(request.base_url).rstrip('/')
    if hasattr(Config, 'PRODUCTION_DOMAIN') and Config.PRODUCTION_DOMAIN:
        base_url = Config.PRODUCTION_DOMAIN
    callback_url = f"{base_url}/api/payment/webhook"
    
    try:
        # Create Plisio invoice
        invoice_data = await create_plisio_invoice(
            amount=amount_usd,
            currency=request_data.currency.value,
            order_name=f"MIMIC {plan['name']} Subscription",
            order_number=order_number,
            callback_url=callback_url,
            email=current_user.email
        )
        
        # Parse expiration time
        expire_utc = invoice_data.get('expire_utc')
        expires_at = None
        if expire_utc:
            try:
                expires_at = datetime.fromisoformat(expire_utc.replace('Z', '+00:00'))
            except:
                expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        else:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        
        # Create payment record
        payment = Payment(
            user_id=current_user.id,
            provider='plisio',
            provider_txn_id=invoice_data.get('txn_id'),
            amount_usd=amount_usd,
            amount_crypto=float(invoice_data.get('amount', 0)),
            currency=request_data.currency.value,
            plan=plan_id,
            days=days,
            status='pending',
            wallet_address=invoice_data.get('wallet_hash') or invoice_data.get('wallet'),
            expires_at=expires_at
        )
        
        db_session.add(payment)
        db_session.commit()
        db_session.refresh(payment)
        
        logger.info(f"✅ Payment invoice created: {order_number} for user {current_user.id}")
        
        return PaymentCreateResponse(
            success=True,
            payment_id=payment.id,
            provider_txn_id=invoice_data.get('txn_id', ''),
            invoice_url=invoice_data.get('invoice_url', ''),
            wallet_address=payment.wallet_address or '',
            amount_usd=amount_usd,
            amount_crypto=payment.amount_crypto or 0,
            currency=request_data.currency.value,
            plan=plan_id,
            days=days,
            expires_at=expires_at,
            message=f"Invoice created. Please complete payment within 24 hours."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Payment creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create payment invoice"
        )


@router_payment.post("/webhook")
async def payment_webhook(
    request: Request,
    db_session: Session = Depends(get_db)
):
    """
    Handle Plisio webhook callbacks
    
    Called by Plisio when payment status changes:
    - new: Invoice created
    - pending: Waiting for confirmations
    - completed: Payment successful
    - expired: Invoice expired
    - error: Payment error
    """
    try:
        # Parse webhook data
        if request.headers.get('content-type', '').startswith('application/json'):
            data = await request.json()
        else:
            form_data = await request.form()
            data = dict(form_data)
        
        txn_id = data.get('txn_id')
        status_value = data.get('status', '').lower()
        verify_hash = data.get('verify_hash')
        
        logger.info(f"📬 Payment webhook received: txn_id={txn_id}, status={status_value}")
        
        # Verify webhook signature
        if verify_hash and not verify_plisio_webhook(data, verify_hash):
            logger.warning(f"⚠️ Invalid webhook signature for txn_id={txn_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid webhook signature"
            )
        
        # Find payment record
        payment = db_session.query(Payment).filter(
            Payment.provider_txn_id == txn_id
        ).first()
        
        if not payment:
            logger.warning(f"⚠️ Payment not found for txn_id={txn_id}")
            return {"status": "ok", "message": "Payment not found"}
        
        # Update payment status
        old_status = payment.status
        
        if status_value == 'completed':
            payment.status = 'completed'
            payment.completed_at = datetime.now(timezone.utc)
            
            # Activate subscription for user
            user = db_session.query(User).filter(User.id == payment.user_id).first()
            if user:
                user.extend_subscription(days=payment.days, plan=payment.plan)
                db_session.commit()
                
                logger.info(f"✅ Subscription activated for user {user.id}: {payment.plan} ({payment.days} days)")
                
                # Send notification
                notifier = get_notifier()
                if notifier and user.telegram_chat_id and user.telegram_enabled:
                    msg = f"""
💎 <b>ПІДПИСКУ АКТИВОВАНО!</b>

✅ <b>План:</b> <code>{payment.plan.upper()}</code>
📅 <b>Днів:</b> <code>{payment.days}</code>
💰 <b>Сума:</b> <code>${payment.amount_usd:.2f}</code>

🚀 Ваша підписка активна до: <code>{user.subscription_expires_at.strftime('%d.%m.%Y %H:%M')}</code>

Дякуємо за покупку! Торгівля тепер увімкнена.
"""
                    notifier.send(msg.strip(), chat_id=user.telegram_chat_id)
        
        elif status_value in ['expired', 'error', 'cancelled']:
            payment.status = status_value
        
        elif status_value in ['pending', 'new']:
            payment.status = 'pending'
        
        db_session.commit()
        
        logger.info(f"📝 Payment {txn_id} status updated: {old_status} -> {payment.status}")
        
        return {"status": "ok", "message": f"Payment status updated to {payment.status}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Webhook processing error: {e}")
        # Return 200 to prevent Plisio from retrying
        return {"status": "error", "message": str(e)}


@router_payment.get("/status/{payment_id}", response_model=PaymentStatusResponse)
async def get_payment_status(
    payment_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db_session: Session = Depends(get_db)
):
    """
    Check payment status
    
    Returns current status of a payment and subscription details if completed.
    """
    payment = db_session.query(Payment).filter(
        Payment.id == payment_id,
        Payment.user_id == current_user.id
    ).first()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    return PaymentStatusResponse(
        payment_id=payment.id,
        status=PaymentStatus(payment.status),
        plan=payment.plan,
        amount_usd=payment.amount_usd,
        created_at=payment.created_at,
        completed_at=payment.completed_at,
        subscription_expires_at=current_user.subscription_expires_at if payment.status == 'completed' else None
    )


@router_payment.get("/subscription", response_model=SubscriptionStatusResponse)
async def get_subscription_status(
    current_user: User = Depends(get_current_user_from_token),
    db_session: Session = Depends(get_db)
):
    """
    Get current subscription status
    
    Returns subscription plan, expiration date, and trading status.
    """
    return SubscriptionStatusResponse(
        is_active=current_user.has_active_subscription(),
        plan=current_user.subscription_plan or 'free',
        expires_at=current_user.subscription_expires_at,
        days_remaining=current_user.subscription_days_remaining(),
        can_trade=current_user.has_active_subscription() and current_user.is_active
    )


@router_payment.get("/history")
async def get_payment_history(
    current_user: User = Depends(get_current_user_from_token),
    db_session: Session = Depends(get_db),
    limit: int = 20,
    offset: int = 0
):
    """
    Get user's payment history
    
    Returns list of all payment transactions for the current user.
    """
    payments = db_session.query(Payment).filter(
        Payment.user_id == current_user.id
    ).order_by(
        Payment.created_at.desc()
    ).offset(offset).limit(limit).all()
    
    total = db_session.query(Payment).filter(
        Payment.user_id == current_user.id
    ).count()
    
    return {
        'success': True,
        'payments': [p.to_dict() for p in payments],
        'total': total,
        'limit': limit,
        'offset': offset
    }

