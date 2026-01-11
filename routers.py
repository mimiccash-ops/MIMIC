"""
FastAPI Routers for Exchange Management System
User and Admin endpoints for managing exchange API keys
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List
import logging

from models import db, User, UserExchange
from schemas import (
    ExchangeCreateRequest,
    ExchangeResponse,
    ExchangeToggleRequest,
    ExchangeToggleResponse,
    PendingExchangeResponse,
    ExchangeApproveRequest,
    ExchangeApproveResponse,
    ExchangeRejectRequest,
    ExchangeRejectResponse,
    ErrorResponse,
    ExchangeStatus,
    SupportedExchange
)
from security import encrypt_secret, decrypt_secret
from service_validator import (
    validate_and_connect,
    ExchangeValidationError,
    ExchangeConnectionError,
    get_exchange_requirements
)
from telegram_notifier import get_notifier, get_email_sender

logger = logging.getLogger("ExchangeAPI")


# ==================== NOTIFICATION HELPERS ====================

def send_exchange_notification(user: User, exchange_name: str, action: str, message: str = None):
    """
    Send notification to user about exchange status change.
    
    Args:
        user: User object
        exchange_name: Name of the exchange
        action: 'approved' or 'rejected'
        message: Optional custom message
    """
    if not user:
        return
    
    # Prepare notification message
    if action == 'approved':
        emoji = "✅"
        default_msg = f"Ваше підключення до {exchange_name.upper()} успішно схвалено! Тепер ви можете активувати його в налаштуваннях."
    else:
        emoji = "❌"
        default_msg = f"Ваше підключення до {exchange_name.upper()} було відхилено."
    
    notification_text = message or default_msg
    
    full_message = f"""
{emoji} <b>EXCHANGE {action.upper()}</b>

📊 <b>Біржа:</b> <code>{exchange_name.upper()}</code>
📝 <b>Статус:</b> <code>{action.upper()}</code>

💬 {notification_text}
"""
    
    # Send via Telegram if enabled
    if user.telegram_enabled and user.telegram_chat_id:
        try:
            notifier = get_notifier()
            if notifier:
                notifier.send(full_message.strip(), chat_id=user.telegram_chat_id)
                logger.info(f"📱 Telegram notification sent to user {user.id}")
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
    
    # Send via Email if available
    if user.email:
        try:
            email_sender = get_email_sender()
            if email_sender and email_sender.enabled:
                subject = f"{'✅' if action == 'approved' else '❌'} Exchange {action.capitalize()} - {exchange_name.upper()}"
                html_content = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family: Arial, sans-serif; background-color: #0a0a12; color: #e8e8f0; padding: 20px;">
    <div style="max-width: 500px; margin: 0 auto; background: #0f0f18; border: 1px solid {'#00f5ff' if action == 'approved' else '#ff4444'}; border-radius: 8px; padding: 30px;">
        <h2 style="color: {'#00f5ff' if action == 'approved' else '#ff4444'}; margin-bottom: 20px;">
            {emoji} Exchange {action.capitalize()}
        </h2>
        <p><strong>Біржа:</strong> {exchange_name.upper()}</p>
        <p><strong>Статус:</strong> {action.upper()}</p>
        <hr style="border-color: #333; margin: 20px 0;">
        <p>{notification_text}</p>
        <p style="color: #666; font-size: 12px; margin-top: 30px;">
            — Brain Capital / MIMIC
        </p>
    </div>
</body>
</html>
"""
                email_sender.send_email(user.email, subject, html_content, notification_text)
                logger.info(f"📧 Email notification sent to user {user.id}")
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")

# Initialize routers
router_user = APIRouter(prefix="/user/exchanges", tags=["User Exchanges"])
router_admin = APIRouter(prefix="/admin/exchanges", tags=["Admin Exchanges"])

# Security scheme - uses HMAC-signed tokens with expiration (see get_current_user)
security = HTTPBearer()


# ==================== DEPENDENCIES ====================

def get_db():
    """
    Database session dependency
    Uses Flask-SQLAlchemy's db.session within Flask app context
    """
    from app import app
    with app.app_context():
        try:
            yield db.session
        finally:
            db.session.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db_session: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user using secure token validation
    
    SECURITY: Uses HMAC signature verification for token integrity
    Token format: base64(user_id:timestamp:signature)
    """
    import hmac
    import hashlib
    import base64
    import time
    from config import Config
    
    TOKEN_MAX_AGE = 3600  # 1 hour token validity
    
    try:
        token = credentials.credentials
        
        # Decode base64 token
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
        
        # Check token expiration
        current_time = int(time.time())
        if current_time - timestamp > TOKEN_MAX_AGE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired"
            )
        
        # Verify HMAC signature
        secret_key = Config.SECRET_KEY.encode() if isinstance(Config.SECRET_KEY, str) else Config.SECRET_KEY
        message = f"{user_id}:{timestamp}".encode()
        expected_signature = hmac.new(secret_key, message, hashlib.sha256).hexdigest()
        
        if not hmac.compare_digest(received_signature, expected_signature):
            logger.warning(f"⚠️ Invalid token signature for user_id={user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token signature"
            )
        
        # Get user from database
        user = db_session.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled"
            )
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )


def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Ensure current user is admin"""
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


# ==================== USER ENDPOINTS ====================

@router_user.post("/", response_model=ExchangeResponse, status_code=status.HTTP_201_CREATED)
async def add_exchange(
    request: ExchangeCreateRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db)
):
    """
    Add a new exchange connection
    
    - Validates exchange credentials using CCXT
    - Encrypts API secret and passphrase
    - Saves to database with status PENDING (requires admin approval)
    """
    try:
        # Check exchange requirements
        requirements = get_exchange_requirements(request.exchange_name.value)
        if not requirements['supported']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Exchange '{request.exchange_name.value}' is not supported"
            )
        
        # Validate passphrase requirement
        if requirements['requires_passphrase'] and not request.passphrase:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Exchange '{request.exchange_name.value}' requires a passphrase"
            )
        
        # Validate and test connection
        try:
            validation_result = validate_and_connect(
                exchange_name=request.exchange_name.value,
                api_key=request.api_key,
                api_secret=request.api_secret,
                passphrase=request.passphrase
            )
            
            if not validation_result['success']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Exchange validation failed"
                )
        
        except ExchangeValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except ExchangeConnectionError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )
        
        # Encrypt secrets
        encrypted_secret = encrypt_secret(request.api_secret)
        encrypted_passphrase = None
        if request.passphrase:
            encrypted_passphrase = encrypt_secret(request.passphrase)
        
        # Create UserExchange record
        # SECURITY: Encrypt API key as well - all credentials are sensitive
        encrypted_api_key = encrypt_secret(request.api_key)
        
        user_exchange = UserExchange(
            user_id=current_user.id,
            exchange_name=request.exchange_name.value,
            label=request.label,
            api_key=encrypted_api_key,  # SECURITY: Now encrypted
            api_secret=encrypted_secret,
            passphrase=encrypted_passphrase,
            status=ExchangeStatus.PENDING.value,
            is_active=False  # Cannot be active until approved
        )
        
        db_session.add(user_exchange)
        db_session.commit()
        db_session.refresh(user_exchange)
        
        logger.info(f"✅ User {current_user.id} added exchange {request.exchange_name.value} (ID: {user_exchange.id})")
        
        return ExchangeResponse(
            id=user_exchange.id,
            user_id=user_exchange.user_id,
            exchange_name=user_exchange.exchange_name,
            label=user_exchange.label,
            status=ExchangeStatus(user_exchange.status),
            is_active=user_exchange.is_active,
            error_message=user_exchange.error_message,
            created_at=user_exchange.created_at,
            updated_at=user_exchange.updated_at
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding exchange: {e}")
        db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add exchange: {str(e)}"
        )


@router_user.get("/", response_model=List[ExchangeResponse])
async def list_my_exchanges(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db)
):
    """
    List all exchanges for the current user
    
    - Hides API secrets
    - Shows status and is_active flag
    """
    try:
        exchanges = db_session.query(UserExchange).filter(
            UserExchange.user_id == current_user.id
        ).all()
        
        return [
            ExchangeResponse(
                id=ex.id,
                user_id=ex.user_id,
                exchange_name=ex.exchange_name,
                label=ex.label,
                status=ExchangeStatus(ex.status),
                is_active=ex.is_active,
                error_message=ex.error_message,
                created_at=ex.created_at,
                updated_at=ex.updated_at
            )
            for ex in exchanges
        ]
    
    except Exception as e:
        logger.error(f"Error listing exchanges: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list exchanges: {str(e)}"
        )


@router_user.patch("/{exchange_id}/toggle", response_model=ExchangeToggleResponse)
async def toggle_exchange(
    exchange_id: int,
    request: ExchangeToggleRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db)
):
    """
    Toggle exchange active status
    
    CRITICAL: Only allows setting is_active=True if status == 'APPROVED'
    """
    try:
        user_exchange = db_session.query(UserExchange).filter(
            UserExchange.id == exchange_id,
            UserExchange.user_id == current_user.id
        ).first()
        
        if not user_exchange:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Exchange not found"
            )
        
        # CRITICAL CHECK: Cannot activate if not approved
        if request.is_active and user_exchange.status != ExchangeStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot activate exchange: Status is '{user_exchange.status}'. "
                       f"Exchange must be APPROVED by an administrator before activation."
            )
        
        user_exchange.is_active = request.is_active
        user_exchange.trading_enabled = request.is_active  # Must set both for trading to work
        db_session.commit()
        db_session.refresh(user_exchange)
        
        logger.info(
            f"User {current_user.id} toggled exchange {exchange_id} to "
            f"{'active' if request.is_active else 'inactive'}"
        )
        
        return ExchangeToggleResponse(
            success=True,
            message=f"Exchange {'activated' if request.is_active else 'deactivated'} successfully",
            exchange=ExchangeResponse(
                id=user_exchange.id,
                user_id=user_exchange.user_id,
                exchange_name=user_exchange.exchange_name,
                label=user_exchange.label,
                status=ExchangeStatus(user_exchange.status),
                is_active=user_exchange.is_active,
                error_message=user_exchange.error_message,
                created_at=user_exchange.created_at,
                updated_at=user_exchange.updated_at
            )
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling exchange: {e}")
        db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle exchange: {str(e)}"
        )


# ==================== ADMIN ENDPOINTS ====================

@router_admin.get("/pending", response_model=List[PendingExchangeResponse])
async def list_pending_exchanges(
    admin_user: User = Depends(get_admin_user),
    db_session: Session = Depends(get_db)
):
    """
    List all pending exchange requests
    
    - Returns all exchanges with status PENDING
    - Includes user information
    """
    try:
        pending_exchanges = db_session.query(UserExchange).filter(
            UserExchange.status == ExchangeStatus.PENDING.value
        ).all()
        
        result = []
        for ex in pending_exchanges:
            user = db_session.query(User).filter(User.id == ex.user_id).first()
            result.append(
                PendingExchangeResponse(
                    id=ex.id,
                    user_id=ex.user_id,
                    user_username=user.username if user else "Unknown",
                    user_email=user.email if user else None,
                    exchange_name=ex.exchange_name,
                    label=ex.label,
                    created_at=ex.created_at
                )
            )
        
        return result
    
    except Exception as e:
        logger.error(f"Error listing pending exchanges: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list pending exchanges: {str(e)}"
        )


@router_admin.post("/{exchange_id}/approve", response_model=ExchangeApproveResponse)
async def approve_exchange(
    exchange_id: int,
    request: ExchangeApproveRequest = None,
    admin_user: User = Depends(get_admin_user),
    db_session: Session = Depends(get_db)
):
    """
    Approve an exchange request
    
    - Updates status to APPROVED
    - Triggers notification to user (mock function)
    """
    try:
        user_exchange = db_session.query(UserExchange).filter(
            UserExchange.id == exchange_id
        ).first()
        
        if not user_exchange:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Exchange not found"
            )
        
        if user_exchange.status != ExchangeStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Exchange status is '{user_exchange.status}', not PENDING"
            )
        
        # Update status
        user_exchange.status = ExchangeStatus.APPROVED.value
        db_session.commit()
        db_session.refresh(user_exchange)
        
        # Get user for notification
        user = db_session.query(User).filter(User.id == user_exchange.user_id).first()
        
        logger.info(
            f"✅ Admin {admin_user.id} approved exchange {exchange_id} "
            f"for user {user_exchange.user_id} ({user.username if user else 'Unknown'})"
        )
        
        # Send actual notification via Telegram and/or Email
        if user:
            notification_message = (
                request.notification_message if request and request.notification_message
                else None  # Use default message from helper
            )
            send_exchange_notification(
                user=user,
                exchange_name=user_exchange.exchange_name,
                action='approved',
                message=notification_message
            )
        
        return ExchangeApproveResponse(
            success=True,
            message=f"Exchange approved successfully",
            exchange=ExchangeResponse(
                id=user_exchange.id,
                user_id=user_exchange.user_id,
                exchange_name=user_exchange.exchange_name,
                label=user_exchange.label,
                status=ExchangeStatus(user_exchange.status),
                is_active=user_exchange.is_active,
                error_message=user_exchange.error_message,
                created_at=user_exchange.created_at,
                updated_at=user_exchange.updated_at
            )
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving exchange: {e}")
        db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve exchange: {str(e)}"
        )


@router_admin.post("/{exchange_id}/reject", response_model=ExchangeRejectResponse)
async def reject_exchange(
    exchange_id: int,
    request: ExchangeRejectRequest,
    admin_user: User = Depends(get_admin_user),
    db_session: Session = Depends(get_db)
):
    """
    Reject an exchange request
    
    - Updates status to REJECTED
    - Stores rejection reason in error_message
    """
    try:
        user_exchange = db_session.query(UserExchange).filter(
            UserExchange.id == exchange_id
        ).first()
        
        if not user_exchange:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Exchange not found"
            )
        
        if user_exchange.status != ExchangeStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Exchange status is '{user_exchange.status}', not PENDING"
            )
        
        # Update status and store rejection reason
        user_exchange.status = ExchangeStatus.REJECTED.value
        user_exchange.error_message = request.reason
        user_exchange.is_active = False  # Ensure it's inactive
        db_session.commit()
        
        # Get user for logging
        user = db_session.query(User).filter(User.id == user_exchange.user_id).first()
        
        logger.info(
            f"❌ Admin {admin_user.id} rejected exchange {exchange_id} "
            f"for user {user_exchange.user_id} ({user.username if user else 'Unknown'}). "
            f"Reason: {request.reason}"
        )
        
        # Send actual notification via Telegram and/or Email
        if user:
            rejection_message = f"Причина: {request.reason}"
            send_exchange_notification(
                user=user,
                exchange_name=user_exchange.exchange_name,
                action='rejected',
                message=rejection_message
            )
        
        return ExchangeRejectResponse(
            success=True,
            message=f"Exchange rejected successfully"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting exchange: {e}")
        db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject exchange: {str(e)}"
        )
