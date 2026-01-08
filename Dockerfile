# Brain Capital - Production Dockerfile
# Multi-stage build for optimized image size

# ==================== BUILD STAGE ====================
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ==================== PRODUCTION STAGE ====================
FROM python:3.11-slim as production

# Security: Run as non-root user
RUN groupadd -r brainapp && useradd -r -g brainapp brainapp

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set Python environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Copy application code
COPY --chown=brainapp:brainapp . .

# Create necessary directories
RUN mkdir -p /app/static/avatars /app/static/music && \
    chown -R brainapp:brainapp /app

# Switch to non-root user
USER brainapp

# Expose port
EXPOSE 5000

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Default command - using Gunicorn with eventlet for SocketIO support
CMD ["python", "-m", "gunicorn", \
    "--worker-class", "eventlet", \
    "--workers", "1", \
    "--bind", "0.0.0.0:5000", \
    "--timeout", "120", \
    "--keep-alive", "5", \
    "--access-logfile", "-", \
    "--error-logfile", "-", \
    "--capture-output", \
    "app:app"]

