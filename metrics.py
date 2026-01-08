"""
Brain Capital - Prometheus Metrics Module
Enterprise-grade observability with prometheus_client

This module provides centralized metric definitions and helpers
for instrumenting the trading platform.

Metrics exposed:
- trade_execution_latency_seconds: Histogram for trade latency
- active_positions_count: Gauge for open positions
- failed_orders_total: Counter for failed order attempts
- successful_orders_total: Counter for successful orders
- active_users_total: Gauge for connected users
- total_aum_usd: Gauge for Assets Under Management
- realized_pnl_usd: Gauge for realized profit/loss
- unrealized_pnl_usd: Gauge for unrealized profit/loss

Usage:
    from metrics import (
        TRADE_LATENCY, ACTIVE_POSITIONS, FAILED_ORDERS,
        track_trade_execution, start_metrics_server
    )
    
    # Track a trade execution
    with track_trade_execution(exchange='binance', symbol='BTCUSDT', action='long'):
        await execute_trade(...)
    
    # Update gauges
    ACTIVE_POSITIONS.labels(exchange='binance').set(5)
"""

import time
import logging
import threading
from contextlib import contextmanager
from functools import wraps
from typing import Optional, Callable

from prometheus_client import (
    Counter, Gauge, Histogram, Info, Summary,
    start_http_server, generate_latest, REGISTRY,
    CollectorRegistry, CONTENT_TYPE_LATEST,
    multiprocess, values
)

logger = logging.getLogger("Metrics")

# ============================================================================
# METRIC DEFINITIONS
# ============================================================================

# Trade execution latency histogram
# Buckets optimized for trading: 10ms to 30s
TRADE_LATENCY = Histogram(
    'trade_execution_latency_seconds',
    'Time taken to execute a trade (copy delay)',
    labelnames=['exchange', 'symbol', 'action', 'status'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
)

# Active positions gauge
ACTIVE_POSITIONS = Gauge(
    'active_positions_count',
    'Number of currently active trading positions',
    labelnames=['exchange', 'symbol']
)

# Failed orders counter
FAILED_ORDERS = Counter(
    'failed_orders_total',
    'Total number of failed order attempts',
    labelnames=['exchange', 'symbol', 'action', 'error_type']
)

# Successful orders counter
SUCCESSFUL_ORDERS = Counter(
    'successful_orders_total',
    'Total number of successful orders',
    labelnames=['exchange', 'symbol', 'action']
)

# Active users gauge
ACTIVE_USERS = Gauge(
    'active_users_total',
    'Number of active trading users',
    labelnames=['exchange', 'user_type']
)

# Total AUM (Assets Under Management)
TOTAL_AUM = Gauge(
    'total_aum_usd',
    'Total assets under management in USD',
    labelnames=['exchange']
)

# Realized PnL
REALIZED_PNL = Gauge(
    'realized_pnl_usd',
    'Realized profit/loss in USD',
    labelnames=['exchange', 'user_type']
)

# Unrealized PnL
UNREALIZED_PNL = Gauge(
    'unrealized_pnl_usd',
    'Unrealized profit/loss in USD',
    labelnames=['exchange', 'user_type']
)

# Signal processing metrics
SIGNALS_RECEIVED = Counter(
    'signals_received_total',
    'Total number of trading signals received',
    labelnames=['symbol', 'action']
)

SIGNALS_PROCESSED = Counter(
    'signals_processed_total',
    'Total number of trading signals fully processed',
    labelnames=['symbol', 'action', 'status']
)

# Rate limit hits
RATE_LIMIT_HITS = Counter(
    'rate_limit_hits_total',
    'Number of times rate limits were hit',
    labelnames=['exchange', 'endpoint']
)

# API call latency
API_LATENCY = Histogram(
    'api_call_latency_seconds',
    'Time taken for exchange API calls',
    labelnames=['exchange', 'endpoint'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

# Worker health
WORKER_TASKS_PROCESSED = Counter(
    'worker_tasks_processed_total',
    'Total tasks processed by the ARQ worker',
    labelnames=['task_name', 'status']
)

WORKER_QUEUE_SIZE = Gauge(
    'worker_queue_size',
    'Current size of the task queue'
)

# Application info
APP_INFO = Info(
    'brain_capital',
    'Brain Capital application information'
)

# ============================================================================
# HELPER FUNCTIONS & DECORATORS
# ============================================================================

@contextmanager
def track_trade_execution(exchange: str, symbol: str, action: str):
    """
    Context manager to track trade execution latency.
    
    Usage:
        with track_trade_execution('binance', 'BTCUSDT', 'long') as tracker:
            result = await execute_trade(...)
            if result.failed:
                tracker.set_status('error', 'api_error')
    
    Args:
        exchange: Exchange name (binance, okx, bybit)
        symbol: Trading pair (BTCUSDT)
        action: Trade action (long, short, close)
    """
    start_time = time.perf_counter()
    status = 'success'
    error_type = None
    
    class Tracker:
        def set_status(self, s: str, err: str = None):
            nonlocal status, error_type
            status = s
            error_type = err
    
    tracker = Tracker()
    
    try:
        yield tracker
    except Exception as e:
        status = 'error'
        error_type = type(e).__name__
        raise
    finally:
        duration = time.perf_counter() - start_time
        TRADE_LATENCY.labels(
            exchange=exchange,
            symbol=symbol,
            action=action,
            status=status
        ).observe(duration)
        
        if status == 'success':
            SUCCESSFUL_ORDERS.labels(
                exchange=exchange,
                symbol=symbol,
                action=action
            ).inc()
        else:
            FAILED_ORDERS.labels(
                exchange=exchange,
                symbol=symbol,
                action=action,
                error_type=error_type or 'unknown'
            ).inc()


def track_api_call(exchange: str, endpoint: str):
    """
    Decorator to track API call latency.
    
    Usage:
        @track_api_call('binance', 'fetch_positions')
        async def get_positions():
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start_time
                API_LATENCY.labels(exchange=exchange, endpoint=endpoint).observe(duration)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start_time
                API_LATENCY.labels(exchange=exchange, endpoint=endpoint).observe(duration)
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def record_rate_limit(exchange: str, endpoint: str = 'general'):
    """Record a rate limit hit."""
    RATE_LIMIT_HITS.labels(exchange=exchange, endpoint=endpoint).inc()


def update_positions(exchange: str, positions: dict):
    """
    Update active positions gauge from a positions dict.
    
    Args:
        exchange: Exchange name
        positions: Dict of {symbol: count} or list of position dicts
    """
    if isinstance(positions, dict):
        for symbol, count in positions.items():
            ACTIVE_POSITIONS.labels(exchange=exchange, symbol=symbol).set(count)
    elif isinstance(positions, list):
        # Reset all positions for this exchange first
        # Then set new values
        symbol_counts = {}
        for pos in positions:
            symbol = pos.get('symbol', 'unknown')
            if symbol not in symbol_counts:
                symbol_counts[symbol] = 0
            contracts = abs(float(pos.get('contracts', 0) or pos.get('positionAmt', 0) or 0))
            if contracts > 0:
                symbol_counts[symbol] += 1
        
        for symbol, count in symbol_counts.items():
            ACTIVE_POSITIONS.labels(exchange=exchange, symbol=symbol).set(count)


def update_aum(exchange: str, balance_usd: float):
    """Update total AUM gauge."""
    TOTAL_AUM.labels(exchange=exchange).set(balance_usd)


def update_pnl(exchange: str, user_type: str, realized: float, unrealized: float):
    """Update PnL gauges."""
    REALIZED_PNL.labels(exchange=exchange, user_type=user_type).set(realized)
    UNREALIZED_PNL.labels(exchange=exchange, user_type=user_type).set(unrealized)


def update_active_users(exchange: str, user_type: str, count: int):
    """Update active users gauge."""
    ACTIVE_USERS.labels(exchange=exchange, user_type=user_type).set(count)


def record_signal(symbol: str, action: str):
    """Record a received trading signal."""
    SIGNALS_RECEIVED.labels(symbol=symbol, action=action).inc()


def record_signal_processed(symbol: str, action: str, status: str = 'success'):
    """Record a processed trading signal."""
    SIGNALS_PROCESSED.labels(symbol=symbol, action=action, status=status).inc()


def record_worker_task(task_name: str, status: str = 'success'):
    """Record a worker task completion."""
    WORKER_TASKS_PROCESSED.labels(task_name=task_name, status=status).inc()


def set_worker_queue_size(size: int):
    """Update worker queue size gauge."""
    WORKER_QUEUE_SIZE.set(size)


def set_app_info(version: str, environment: str = 'production'):
    """Set application info labels."""
    APP_INFO.info({
        'version': version,
        'environment': environment,
        'name': 'brain_capital'
    })


# ============================================================================
# METRICS SERVER
# ============================================================================

_metrics_server_started = False
_metrics_server_lock = threading.Lock()


def start_metrics_server(port: int = 9091):
    """
    Start Prometheus metrics HTTP server.
    
    This starts a background thread serving metrics on the specified port.
    Safe to call multiple times - only starts once.
    
    Args:
        port: Port to serve metrics on (default: 9091)
    """
    global _metrics_server_started
    
    with _metrics_server_lock:
        if _metrics_server_started:
            logger.debug(f"Metrics server already running")
            return
        
        try:
            start_http_server(port)
            _metrics_server_started = True
            logger.info(f"📊 Prometheus metrics server started on port {port}")
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")


def get_metrics():
    """
    Get current metrics in Prometheus format.
    
    Returns:
        Tuple of (metrics_bytes, content_type)
    """
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


# ============================================================================
# FLASK INTEGRATION
# ============================================================================

def init_flask_metrics(app):
    """
    Initialize metrics endpoint for Flask app.
    
    Adds /metrics endpoint to the Flask application.
    
    Args:
        app: Flask application instance
    """
    from flask import Response
    
    @app.route('/metrics')
    def metrics_endpoint():
        metrics_output, content_type = get_metrics()
        return Response(metrics_output, mimetype=content_type)
    
    logger.info("📊 Flask /metrics endpoint registered")


# ============================================================================
# FASTAPI INTEGRATION
# ============================================================================

def get_fastapi_metrics_route():
    """
    Get FastAPI route handler for metrics.
    
    Usage:
        from metrics import get_fastapi_metrics_route
        from fastapi import APIRouter
        
        router = APIRouter()
        router.add_api_route('/metrics', get_fastapi_metrics_route())
    
    Returns:
        Async function that returns metrics response
    """
    from fastapi.responses import Response
    
    async def metrics_endpoint():
        metrics_output, content_type = get_metrics()
        return Response(content=metrics_output, media_type=content_type)
    
    return metrics_endpoint


# Initialize app info on module load
set_app_info(version='3.0.0', environment='production')

