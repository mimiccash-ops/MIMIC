"""
FastAPI Application for Exchange Management System
Main entry point for FastAPI endpoints
"""

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import time
import secrets
from contextlib import asynccontextmanager

from models import db
from routers import router_user, router_admin
from payment_router import router_payment
from schemas import ErrorResponse
from public_api import public_api


# ==================== SECURITY MIDDLEWARE ====================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' https:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        
        # Add request ID for tracing
        response.headers["X-Request-ID"] = secrets.token_hex(8)
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware"""
    
    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}  # {ip: [(timestamp, count)]}
    
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        
        # Clean old entries and check rate
        if client_ip in self.requests:
            self.requests[client_ip] = [
                (ts, count) for ts, count in self.requests[client_ip]
                if current_time - ts < self.window_seconds
            ]
        else:
            self.requests[client_ip] = []
        
        request_count = sum(count for _, count in self.requests[client_ip])
        
        if request_count >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"error": "Too many requests. Please try again later."}
            )
        
        self.requests[client_ip].append((current_time, 1))
        
        response = await call_next(request)
        return response

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("FastAPI")

# ==================== SENTRY ERROR TRACKING ====================
# Optional: Set SENTRY_DSN environment variable to enable error tracking
try:
    from sentry_config import init_sentry
    SENTRY_ENABLED = init_sentry(framework='fastapi')
except ImportError:
    SENTRY_ENABLED = False
    logger.info("Sentry not configured (optional)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    # Startup
    logger.info("🚀 FastAPI Exchange Management API starting...")
    
    # Initialize Flask app context for database access
    from app import app as flask_app
    flask_app.app_context().push()
    
    # Initialize database (if needed)
    try:
        # Create tables if they don't exist
        from models import db
        db.create_all()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
    
    yield
    
    # Shutdown
    logger.info("🛑 FastAPI Exchange Management API shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Exchange Management API",
    description="Crypto Copy-Trading Bot - Exchange Management System",
    version="1.0.0",
    lifespan=lifespan
)

# ==================== SECURITY CONFIGURATION ====================
# CORS middleware - PRODUCTION HARDENED
# Configure via PRODUCTION_DOMAIN environment variable
# Example: PRODUCTION_DOMAIN=https://yourdomain.com,https://www.yourdomain.com

import os
IS_PRODUCTION = os.environ.get('FLASK_ENV', 'development') == 'production'
PRODUCTION_DOMAIN = os.environ.get('PRODUCTION_DOMAIN', '')

if IS_PRODUCTION and PRODUCTION_DOMAIN:
    # In production, only allow the configured domain(s)
    ALLOWED_ORIGINS = [origin.strip() for origin in PRODUCTION_DOMAIN.split(',')]
else:
    # Development origins
    ALLOWED_ORIGINS = [
        "http://localhost",
        "http://localhost:80",
        "http://localhost:5000",
        "http://localhost:8000",
        "http://127.0.0.1",
        "http://127.0.0.1:80",
        "http://127.0.0.1:5000",
        "http://127.0.0.1:8000",
        "http://38.180.143.20",
        "http://38.180.143.20:80",
        "https://38.180.143.20",
        "http://mimic.cash",
        "https://mimic.cash",
        "http://www.mimic.cash",
        "https://www.mimic.cash",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # Restrict to known origins only
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],  # Explicit methods
    allow_headers=["Content-Type", "Authorization", "X-Requested-With", "X-CSRF-Token"],
    expose_headers=["X-Request-ID"],
    max_age=600,  # Cache preflight for 10 minutes
)

# Add security middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60)

# Include routers
app.include_router(router_user)
app.include_router(router_admin)
app.include_router(router_payment)

# Mount Public API under /api/v1 prefix
# For production, this can also be served separately on api.mimic.cash
app.mount("/api/public", public_api)


# ==================== ROOT & HEALTH CHECK ====================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Exchange Management API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Exchange Management API"
    }


# ==================== ERROR HANDLERS ====================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            code=str(exc.status_code)
        ).dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """General exception handler - NEVER expose internal errors to clients"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Internal server error",
            detail=None,  # SECURITY: Never expose exception details to clients
            code="500"
        ).dict()
    )


if __name__ == "__main__":
    import uvicorn
    
    # Run with uvicorn
    uvicorn.run(
        "app_fastapi:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Set to False in production
        log_level="info"
    )
