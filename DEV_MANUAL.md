# 🧠 MIMIC (Brain Capital) - Developer Manual

**Copy Trading Platform for Cryptocurrency Exchanges**

Version: 3.0  
Last Updated: January 6, 2026  
Code Audit Date: January 6, 2026

---

## 📑 Table of Contents

1. [Project Overview](#-project-overview)
2. [Architecture](#-architecture)
3. [Quick Start](#-quick-start)
4. [Environment Variables](#-environment-variables)
5. [Project Structure](#-project-structure)
6. [Core Modules](#-core-modules)
7. [API Endpoints](#-api-endpoints)
8. [Database Schema](#-database-schema)
9. [Security Features](#-security-features)
10. [Technical Debt & TODOs](#-technical-debt--todos)
11. [Production Deployment](#-production-deployment)
12. [Troubleshooting](#-troubleshooting)
13. [Development Workflow](#-development-workflow)
14. [File Inventory](#-file-inventory)

---

## 🎯 Project Overview

**MIMIC (Brain Capital)** is an automated copy-trading platform that enables users to copy trades from a master account across multiple cryptocurrency exchanges (primarily Binance Futures). It receives trading signals via TradingView webhooks and executes them across all connected user accounts.

### Key Features

| Feature | Description |
|---------|-------------|
| 🔄 **Automatic Copy Trading** | Users automatically copy master account trades |
| 📊 **TradingView Webhooks** | Integration with TradingView alerts |
| 🔐 **API Key Encryption** | Secure storage of exchange API keys using Fernet |
| 📱 **Telegram Notifications** | Real-time trade alerts and system notifications |
| 📧 **Email Notifications** | Password recovery via SMTP |
| 📈 **Real-time Dashboard** | Live position monitoring via WebSockets |
| 👥 **User Management** | Admin panel for managing users/nodes |
| 🛡️ **Risk Controls** | Configurable risk, leverage, TP/SL settings |
| 🌐 **Multi-Exchange Support** | Support for 30+ exchanges via CCXT |
| 🔒 **2FA Panic Kill Switch** | Emergency position close via Telegram with OTP |
| 📬 **Internal Messaging** | User-admin messaging system |
| 👤 **Referral System** | Built-in referral tracking with commissions |
| 💳 **Subscription System** | Crypto payments via Plisio gateway |
| 📉 **Smart Features** | Trailing Stop-Loss, DCA, Risk Guardrails |

### Supported Exchanges

**Tier 1 (Major):** Binance, Coinbase, Bybit, OKX, Upbit  
**Tier 2 (Large):** Bitget, Gate, KuCoin, Kraken, HTX  
**Tier 3 (Mid-size):** MEXC, Crypto.com, Bitstamp, Bitfinex, Bithumb  
**Tier 4+:** WhiteBit, Poloniex, Gemini, BingX, Phemex, and more

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           CLIENT LAYER                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐ │
│  │ Web Browser │  │ TradingView │  │     Telegram Bot            │ │
│  │ (Dashboard) │  │  (Webhooks) │  │   (Notifications + OTP)     │ │
│  └──────┬──────┘  └──────┬──────┘  └─────────────────────────────┘ │
└─────────┼────────────────┼───────────────────────────────────────────┘
          │                │
          ▼                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         APPLICATION LAYER                            │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                      Flask Application (app.py)                 ││
│  │  ├─ /webhook      → TradingView signal processing              ││
│  │  ├─ /login        → User authentication                        ││
│  │  ├─ /dashboard    → User/Admin dashboards                      ││
│  │  └─ /api/*        → REST API endpoints                         ││
│  └─────────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    FastAPI (app_fastapi.py)                     ││
│  │  ├─ /user/exchanges/*   → User exchange management             ││
│  │  ├─ /admin/exchanges/*  → Admin approval workflow              ││
│  │  └─ /api/payment/*      → Subscription payments                ││
│  └─────────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                      Flask-SocketIO                             ││
│  │  └─ Real-time updates (balance, positions, trades)             ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          SERVICE LAYER                               │
│  ┌─────────────────┐  ┌────────────────┐  ┌──────────────────────┐ │
│  │ Trading Engine  │  │ Telegram       │  │ Email Sender         │ │
│  │ (Copy Trading)  │  │ Notifier + Bot │  │ (SMTP)               │ │
│  └────────┬────────┘  └────────────────┘  └──────────────────────┘ │
│           │                                                         │
│  ┌────────▼────────┐  ┌────────────────┐  ┌──────────────────────┐ │
│  │ Exchange        │  │ Security       │  │ Smart Features       │ │
│  │ Clients (CCXT)  │  │ Module         │  │ (Trailing/DCA/Risk)  │ │
│  └────────┬────────┘  └────────────────┘  └──────────────────────┘ │
└───────────┼─────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          DATA LAYER                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────────┐│
│  │ SQLite/PostgreSQL│  │ Redis (Optional)│  │ Exchange APIs       ││
│  │ (User Data)     │  │ (Task Queue)    │  │ (Binance, etc.)     ││
│  └─────────────────┘  └─────────────────┘  └──────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Component | Technology | Notes |
|-----------|------------|-------|
| **Backend Framework** | Flask 3.0 + FastAPI | Flask for main app, FastAPI for exchange/payment mgmt |
| **Database** | SQLite (dev) / PostgreSQL (prod) | SQLAlchemy 2.0 ORM with optimized indexes |
| **Authentication** | Flask-Login | Session-based with fingerprinting |
| **Real-time** | Flask-SocketIO | WebSocket updates for dashboard |
| **Exchange API** | python-binance + CCXT | CCXT for multi-exchange support |
| **Encryption** | Fernet (cryptography) | API key encryption |
| **Task Queue** | ARQ + Redis (optional) | Async background processing |
| **2FA** | PyOTP | TOTP for panic kill switch |
| **Payments** | Plisio | Crypto payment gateway |
| **Observability** | Prometheus + Loki | Metrics and logging |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+** (3.13 recommended)
- **Git**
- **(Optional)** Redis 6.0+ for task queue
- **(Optional)** PostgreSQL 14+ for production

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd "MIMIC v3.0"

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Generate security keys (creates .env file)
python setup_env.py

# Copy and configure config.ini
copy config.ini.example config.ini
# Edit config.ini with your Binance API keys and settings
```

### 3. Run the Application

**Development Mode:**
```bash
# Windows
python app.py

# Or using batch file
run_bot.bat
```

**Production Mode:**
```bash
# Windows (as Administrator for port 80)
python run_server.py

# Or use deployment script
deploy_production.bat

# Or PowerShell (with firewall setup)
.\deploy_production.ps1
```

### 4. Access the Application

- **Local**: http://localhost (or http://localhost:80)
- **Default Login**: `admin` / `admin`

> ⚠️ **IMPORTANT**: Change the default admin password immediately after first login!

---

## 🔧 Environment Variables

### Required Variables (.env file)

| Variable | Description | Example |
|----------|-------------|---------|
| `FLASK_SECRET_KEY` | Flask session signing key (32+ chars) | `<secrets.token_hex(32)>` |
| `BRAIN_CAPITAL_MASTER_KEY` | Fernet key for encrypting API keys | `<Fernet.generate_key()>` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_ENV` | Environment mode (`development`/`production`) | `development` |
| `DATABASE_URL` | PostgreSQL connection string | SQLite (local) |
| `REDIS_URL` | Redis connection URL | None (in-memory) |
| `PRODUCTION_DOMAIN` | Production domain(s) for CORS | `https://mimic.cash` |
| `HTTPS_ENABLED` | Enable HTTPS | `false` |
| `PLISIO_API_KEY` | Plisio payment gateway API key | None |
| `PLISIO_WEBHOOK_SECRET` | Plisio webhook verification secret | None |

### Generate Security Keys

```python
# Generate FLASK_SECRET_KEY
import secrets
print(secrets.token_hex(32))

# Generate BRAIN_CAPITAL_MASTER_KEY (Fernet)
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

### Configuration Files

| File | Purpose | Commit to Git? |
|------|---------|----------------|
| `.env` | Secret keys | ❌ NO |
| `config.ini` | API keys, settings | ❌ NO |
| `config.ini.example` | Template | ✅ YES |
| `production.env.example` | Template | ✅ YES |
| `brain_capital.db` | SQLite database | ❌ NO |

---

## 📁 Project Structure

```
MIMIC v3.0/
│
├── 📄 Core Application
│   ├── app.py                    # Main Flask application (4300+ lines)
│   ├── app_fastapi.py            # FastAPI for exchange/payment management
│   ├── config.py                 # Configuration with env validation
│   ├── models.py                 # SQLAlchemy database models
│   ├── routers.py                # FastAPI routers (user/admin exchanges)
│   ├── schemas.py                # Pydantic schemas for FastAPI
│   ├── security.py               # Security module (rate limiting, auth, encryption)
│   ├── trading_engine.py         # Copy trading engine (async, multi-exchange)
│   ├── telegram_notifier.py      # Telegram & Email notifications
│   ├── telegram_bot.py           # Telegram bot with OTP kill switch
│   ├── service_validator.py      # Exchange validation via CCXT
│   ├── payment_router.py         # Plisio crypto payment integration
│   ├── smart_features.py         # Trailing SL, DCA, Risk Guardrails
│   ├── metrics.py                # Prometheus metrics
│   └── run_server.py             # Production server launcher
│
├── 📄 Configuration
│   ├── config.ini                # Runtime config (DO NOT COMMIT)
│   ├── config.ini.example        # Configuration template
│   ├── .env                      # Environment secrets (DO NOT COMMIT)
│   ├── production.env.example    # Production env template
│   └── requirements.txt          # Python dependencies
│
├── 📄 Background Tasks (Optional)
│   ├── worker.py                 # ARQ worker for async tasks
│   └── tasks.py                  # Task definitions
│
├── 📄 Utilities & Scripts
│   ├── setup_env.py              # Generate .env file
│   ├── add_performance_indexes.py # Database optimization
│   ├── migrate_add_columns.py    # Migration: add columns
│   ├── migrate_add_smart_features.py # Migration: smart features
│   ├── migrate_add_risk_guardrails.py # Migration: risk guardrails
│   ├── migrate_add_subscription.py # Migration: subscription system
│   ├── migrate_sqlite_to_postgres.py # Database migration
│   ├── optimize_assets.py        # JS/CSS minification
│   └── stress_test.py            # Load testing (1000+ users)
│
├── 📄 Deployment
│   ├── run_bot.bat               # Development launcher (Windows)
│   ├── run_production.bat        # Production with waitress
│   ├── deploy_production.bat     # Full deployment script
│   ├── deploy_production.ps1     # PowerShell deployment
│   ├── START_PRODUCTION.bat      # Quick production start
│   ├── run_production.sh         # Linux production script
│   ├── fix_port.bat              # Free port 80 (Windows)
│   ├── run_worker.bat            # Start ARQ worker
│   ├── Dockerfile                # Docker container
│   ├── docker-compose.yml        # Docker orchestration (full stack)
│   └── nginx.conf.example        # Nginx reverse proxy config
│
├── 📂 static/                    # Static assets
│   ├── css/
│   │   ├── main.css              # Main stylesheet (4400+ lines)
│   │   └── main.min.css          # Minified CSS
│   ├── js/
│   │   ├── main.js               # Main JavaScript (3200+ lines)
│   │   └── main.min.js           # Minified JS
│   ├── avatars/                  # User avatar uploads
│   ├── manifest.json             # PWA manifest
│   ├── mimic-logo.svg            # Logo
│   ├── og-image.svg              # Social media preview
│   ├── robots.txt                # SEO
│   └── sitemap.xml               # SEO
│
├── 📂 templates/                 # Jinja2 HTML templates
│   ├── base.html                 # Base template with layout
│   ├── index.html                # Landing page
│   ├── login.html                # Login page
│   ├── register.html             # Registration with referral
│   ├── dashboard_admin.html      # Admin dashboard
│   ├── dashboard_user.html       # User dashboard
│   ├── leaderboard.html          # User leaderboard
│   ├── messages_user.html        # User messages inbox
│   ├── messages_admin.html       # Admin messages
│   ├── message_view_user.html    # Message thread view
│   ├── message_view_admin.html   # Admin message view
│   ├── forgot_password.html      # Password reset request
│   ├── reset_password.html       # Password reset form
│   └── change_password.html      # Change password
│
├── 📂 docker/                    # Docker configuration
│   └── init-db/                  # Database initialization scripts
│
├── 📂 monitoring/                # Observability stack
│   ├── grafana/
│   │   ├── dashboards/           # Pre-configured dashboards
│   │   └── provisioning/         # Auto-provisioning configs
│   ├── loki/
│   │   └── loki-config.yml       # Log aggregation config
│   ├── prometheus/
│   │   ├── prometheus.yml        # Metrics scraping config
│   │   └── alerts.yml            # Alert rules
│   └── promtail/
│       └── promtail-config.yml   # Log shipping config
│
├── 📂 secrets/                   # Local secrets (development)
│   └── master.key                # Fernet key file (DO NOT COMMIT)
│
├── 📂 logs/                      # Application logs
│
└── 📄 Documentation
    ├── README.md                 # Project overview
    ├── DEV_MANUAL.md             # This file
    ├── SECURITY.md               # Security guidelines
    ├── SECURITY_HARDENING.md     # Production hardening
    └── README_EXCHANGE_MANAGEMENT.md # Exchange API docs
```

---

## 🔌 Core Modules

### `app.py` - Main Flask Application

The heart of the application containing:
- Flask app initialization and configuration
- All web routes (login, register, dashboard, webhooks)
- WebSocket event handlers (Flask-SocketIO)
- Admin functionality
- User profile management
- Position monitoring threads

**Key Functions:**
- `process_webhook()` - TradingView signal processing
- `update_balances()` - Real-time balance updates via WebSocket
- `panic_close_all()` - Emergency position closure

### `trading_engine.py` - Copy Trading Engine

Handles all trading operations:
- Master/slave account management
- Position opening/closing with TP/SL
- Multi-exchange support via CCXT (async)
- Rate limiting per exchange
- Proxy pool for high-volume trading

**Key Classes:**
- `TradingEngine` - Main trading orchestrator
- `RateLimiter` - API call throttling (async-safe)
- `ProxyPool` - Proxy rotation for scaling

### `smart_features.py` - Advanced Trading Features

Implements:
- **Trailing Stop-Loss** - Dynamic SL stored in Redis (hidden from market)
- **DCA (Dollar Cost Averaging)** - Automatic position averaging on drawdown
- **Risk Guardrails** - Daily equity protection (drawdown stop & profit lock)

**Key Classes:**
- `SmartFeaturesManager` - Trailing SL + DCA management
- `RiskGuardrailsManager` - Daily equity protection

### `security.py` - Security Module

Comprehensive security implementation:
- Rate limiting (per IP, per user, per endpoint)
- Login tracking and IP blocking with escalation
- Input validation and sanitization
- CSRF protection
- Session fingerprinting
- Security headers middleware
- API token generation (HMAC-signed)
- Encryption/decryption services

### `models.py` - Database Models

SQLAlchemy models with optimized indexes:
- `User` - User accounts with encrypted API keys
- `TradeHistory` - Trade records with PnL
- `BalanceHistory` - Balance snapshots
- `UserExchange` - Multi-exchange connections
- `ExchangeConfig` - Admin exchange configuration
- `Message` - Internal messaging
- `ReferralCommission` - Referral tracking
- `Payment` - Subscription payments
- `PasswordResetToken` - Password recovery

### `payment_router.py` - Crypto Payments

Plisio payment gateway integration:
- Invoice creation (USDT, BTC, ETH, LTC)
- Webhook handling for payment confirmation
- Subscription activation/extension
- Payment history

---

## 🔌 API Endpoints

### Flask Routes (app.py)

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/` | GET | No | Landing page |
| `/login` | GET/POST | No | User authentication |
| `/logout` | GET | Yes | User logout |
| `/register` | GET/POST | No | User registration |
| `/dashboard` | GET | Yes | User/Admin dashboard |
| `/webhook` | POST | Passphrase | TradingView webhook |
| `/api/balance` | GET | Yes | Current balance |
| `/api/balance_history` | GET | Yes | Balance history |
| `/api/positions` | GET | Yes | Open positions |
| `/api/trades` | GET | Yes | Trade history |
| `/api/profile` | GET/POST | Yes | Profile management |
| `/forgot-password` | GET/POST | No | Password reset request |
| `/reset-password/<token>` | GET/POST | No | Password reset |
| `/leaderboard` | GET | No | Public leaderboard |

### Admin Routes

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/admin/users` | GET | Admin | List all users |
| `/admin/user/<id>` | GET/POST/DELETE | Admin | User management |
| `/admin/settings` | GET/POST | Admin | Global trading settings |
| `/admin/panic` | POST | Admin | Emergency close all |

### FastAPI Routes (app_fastapi.py)

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | No | Health check |
| `/user/exchanges/` | GET | Bearer | List user's exchanges |
| `/user/exchanges/` | POST | Bearer | Add new exchange |
| `/user/exchanges/{id}/toggle` | PATCH | Bearer | Enable/disable |
| `/admin/exchanges/pending` | GET | Admin | List pending approvals |
| `/admin/exchanges/{id}/approve` | POST | Admin | Approve exchange |
| `/admin/exchanges/{id}/reject` | POST | Admin | Reject exchange |

### Payment Routes (payment_router.py)

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/payment/plans` | GET | No | Get subscription plans |
| `/api/payment/create` | POST | Bearer | Create payment invoice |
| `/api/payment/webhook` | POST | Webhook | Plisio callback |
| `/api/payment/status/{id}` | GET | Bearer | Check payment status |
| `/api/payment/subscription` | GET | Bearer | Subscription status |
| `/api/payment/history` | GET | Bearer | Payment history |

### Webhook Format

```json
{
    "passphrase": "your_secret_passphrase",
    "symbol": "BTCUSDT",
    "action": "long",
    "risk_perc": 3,
    "leverage": 20,
    "tp_perc": 5,
    "sl_perc": 2
}
```

**Supported Actions:** `long`, `short`, `close`

---

## 🗄 Database Schema

### Core Tables

#### users
| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| username | String(50) | Unique username (indexed) |
| password_hash | String(256) | Hashed password (scrypt) |
| email | String(120) | Email address (indexed) |
| api_key_enc | String(500) | Encrypted Binance API key |
| api_secret_enc | String(500) | Encrypted Binance secret |
| is_active | Boolean | Account active status |
| is_paused | Boolean | Trading paused |
| role | String(20) | 'user' or 'admin' |
| custom_risk | Float | Custom risk percentage |
| custom_leverage | Integer | Custom leverage |
| telegram_chat_id | String(50) | Telegram notification ID |
| referral_code | String(20) | User's referral code |
| referred_by_id | Integer | FK to referrer |
| subscription_plan | String(50) | Current subscription |
| subscription_expires_at | DateTime | Subscription expiry |
| dca_enabled | Boolean | DCA enabled |
| trailing_sl_enabled | Boolean | Trailing SL enabled |
| risk_guardrails_enabled | Boolean | Risk guardrails enabled |

#### trade_history
| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| user_id | Integer | FK to users |
| symbol | String(20) | Trading pair |
| side | String(10) | LONG/SHORT |
| pnl | Float | Profit/Loss |
| roi | Float | Return on Investment |
| close_time | DateTime | Trade close timestamp |

#### user_exchanges
| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| user_id | Integer | FK to users |
| exchange_name | String(50) | Exchange identifier |
| api_key | String(500) | Encrypted API key |
| api_secret | String(500) | Encrypted API secret |
| status | String(20) | PENDING/APPROVED/REJECTED |
| is_active | Boolean | Exchange enabled |
| trading_enabled | Boolean | Trading allowed |

#### payments
| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| user_id | Integer | FK to users |
| provider_txn_id | String(200) | Plisio transaction ID |
| amount_usd | Float | Amount in USD |
| plan | String(50) | Subscription plan |
| status | String(30) | pending/completed/expired |

---

## 🛡 Security Features

### Implemented Security Measures

| Feature | Implementation |
|---------|----------------|
| **Password Hashing** | Scrypt algorithm via Werkzeug |
| **API Key Encryption** | Fernet symmetric encryption |
| **Rate Limiting** | Per-IP/user throttling with escalation |
| **CSRF Protection** | Token-based CSRF prevention |
| **Session Security** | Fingerprinting, secure cookies |
| **Input Validation** | SQL injection/XSS prevention |
| **Security Headers** | X-Frame-Options, CSP, etc. |
| **Login Tracking** | Failed attempt monitoring & IP blocking |
| **HMAC Token Auth** | Secure API token generation |
| **2FA Kill Switch** | OTP verification for panic commands |

### Security Checklist for Production

- [ ] Change default admin password immediately
- [ ] Use HTTPS in production (SSL certificate)
- [ ] Set strong `FLASK_SECRET_KEY` (32+ characters)
- [ ] Set `FLASK_ENV=production`
- [ ] Configure IP whitelist on exchange API keys
- [ ] Enable Telegram 2FA notifications
- [ ] Set up `PANIC_OTP_SECRET` for kill switch
- [ ] Review `SECURITY_HARDENING.md`

---

## 📋 Technical Debt & TODOs

### Code Audit Summary (January 6, 2026)

**Audit Scope:** Full codebase review including backend, frontend, configuration, and deployment scripts.

#### Active TODO Comments in Code

| File | Line | TODO Description | Priority |
|------|------|------------------|----------|
| `smart_features.py` | 322 | `TODO: Implement actual position close via exchange` - Trailing SL trigger execution needs user's exchange client integration | 🔴 High |

**Search command used:** `grep -rn "TODO\|FIXME\|HACK\|XXX\|BUG" --include="*.py"`

#### Debug Statements Found (Safe - Development Use Only)

The following files contain `logger.debug()` statements which are appropriate for development and don't expose sensitive data in production (log level is INFO by default):

- `app.py` - Webhook health check, password reset, position updates
- `trading_engine.py` - Leverage settings, position monitoring, DCA checks
- `config.py` - Secret loading diagnostics
- `metrics.py` - Metrics server status
- `security.py` - Rate limiter cleanup

### Resolved Issues

| Issue | Status | Date |
|-------|--------|------|
| Hardcoded secrets in batch scripts | ✅ **Removed** | Jan 2026 |
| Exchange notification implementation | ✅ Fixed in `routers.py` | Jan 2026 |
| Payment system integration | ✅ Added Plisio | Jan 2026 |
| Subscription management | ✅ Full implementation | Jan 2026 |
| Multi-exchange support | ✅ 30+ exchanges via CCXT | Jan 2026 |
| Risk guardrails | ✅ Daily drawdown/profit lock | Jan 2026 |
| DCA (Dollar Cost Averaging) | ✅ Automatic position averaging | Jan 2026 |
| Trailing Stop-Loss | ✅ Redis-based hidden SL | Jan 2026 |

### Recommendations

#### 🔴 High Priority
1. **Complete trailing SL execution** - Implement the TODO in `smart_features.py:322` to actually close positions when trailing SL is triggered
2. **Add comprehensive unit/integration tests** - No test suite exists; recommend pytest with fixtures for database testing
3. **Set up CI/CD pipeline** - GitHub Actions workflow for automated testing and deployment
4. **Database migrations with Alembic** - Currently using manual migration scripts; migrate to Alembic for version control

#### 🟡 Medium Priority
1. **Implement Celery for task queue** - ARQ works but Celery is more robust with better monitoring
2. **Centralized logging with Loki** - Currently configured but needs production tuning
3. **API documentation** - FastAPI has built-in OpenAPI; add more detailed docstrings
4. **WebSocket reconnection logic** - Improve client-side reconnection handling

#### 🟢 Low Priority
1. **User API rate limiting per subscription tier** - Different limits for Basic/Pro/Enterprise
2. **Error tracking with Sentry** - Production error monitoring
3. **APM integration** - Application Performance Monitoring for bottleneck detection
4. **Image optimization** - WebP conversion for avatars and assets

### Known Limitations

| Limitation | Workaround | Planned Fix |
|------------|------------|-------------|
| SQLite in production | Use PostgreSQL | Automatic detection in config.py |
| Single server deployment | Load balancer ready | Docker Swarm/K8s guide needed |
| No automated backups | `backup_db.sh` script available | Cron job setup in docs |
| Trailing SL execution incomplete | Manual monitoring | Complete TODO |

### Files Reviewed - All Active

All files in the project are actively used. No orphan or unused files were found during the audit.

---

## 🚢 Production Deployment

### Windows Server Deployment

**Option 1: Quick Start**
```batch
# Run as Administrator
deploy_production.bat
```

**Option 2: PowerShell (with firewall setup)**
```powershell
# Right-click -> Run as Administrator
.\deploy_production.ps1
```

**Option 3: Manual**
```bash
# Set environment
set FLASK_ENV=production
set PRODUCTION_DOMAIN=https://yourdomain.com

# Run with production server
python run_server.py
```

### Linux Deployment (with Gunicorn)

```bash
# Install gunicorn
pip install gunicorn gevent gevent-websocket

# Run with gunicorn
gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker \
         -w 4 -b 0.0.0.0:80 app:app
```

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f web

# Scale workers
docker-compose up -d --scale worker=3
```

### Nginx Configuration

```nginx
server {
    listen 80;
    server_name mimic.cash www.mimic.cash;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name mimic.cash www.mimic.cash;

    ssl_certificate /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /socket.io/ {
        proxy_pass http://127.0.0.1:5000/socket.io/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Production Checklist

- [ ] Set `FLASK_ENV=production`
- [ ] Configure PostgreSQL database
- [ ] Set up Redis for caching/sessions
- [ ] Configure SSL/HTTPS
- [ ] Set up monitoring (logs, metrics)
- [ ] Configure automatic backups
- [ ] Test webhook connectivity
- [ ] Verify Telegram notifications work
- [ ] Configure firewall rules

---

## 🔧 Troubleshooting

### Common Issues

#### Port 80 Already in Use
```batch
# Windows - Free port 80
fix_port.bat

# Or manually find process
netstat -ano | findstr :80
taskkill /PID <pid> /F
```

#### Encryption Error
```bash
# Regenerate encryption keys
python setup_env.py --force
```

#### Database Locked (SQLite)
```bash
# Run database optimization
python add_performance_indexes.py
```

#### Binance API Error
- Check API key permissions (Enable Futures)
- Verify IP whitelist includes server IP
- Check testnet vs mainnet setting in config.ini

#### WebSocket Connection Failed
- Check firewall allows WebSocket traffic
- Verify nginx proxy configuration
- Check CORS settings match your domain

### Logs

```bash
# Application logs are printed to console
# Check for error patterns:
# - "❌" = Error
# - "⚠️" = Warning
# - "✅" = Success

# Database queries (enable in development)
# Set SQLALCHEMY_ECHO=True in config
```

---

## 💻 Development Workflow

### Setting Up Development Environment

1. **Clone and install:**
   ```bash
   git clone <repository>
   cd "MIMIC v3.0"
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure:**
   ```bash
   python setup_env.py
   copy config.ini.example config.ini
   # Edit config.ini with your test API keys
   ```

3. **Run development server:**
   ```bash
   python app.py
   ```

### Code Style

- Follow PEP 8 guidelines
- Use type hints where possible
- Document functions with docstrings
- Use logging instead of print statements
- Emojis in log messages: ✅ success, ❌ error, ⚠️ warning, 🔄 processing

### Testing Changes

1. **Run the stress test:**
   ```bash
   python stress_test.py --users 100
   ```

2. **Test webhook manually:**
   ```bash
   curl -X POST http://localhost/webhook \
     -H "Content-Type: application/json" \
     -d '{"passphrase":"your_passphrase","symbol":"BTCUSDT","action":"long"}'
   ```

### Database Migrations

Currently manual. When changing models:
1. Update `models.py`
2. Create migration script in `migrate_*.py`
3. Run migration: `python migrate_*.py`

For production, use the migration script:
```bash
python migrate_sqlite_to_postgres.py
```

---

## 📦 File Inventory

### Core Python Files

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `app.py` | ~4347 | Main Flask application with all web routes, WebSocket handlers, and admin functionality | ✅ Active |
| `app_fastapi.py` | ~242 | FastAPI server for exchange management and payment APIs | ✅ Active |
| `trading_engine.py` | ~3825 | Copy trading engine with multi-exchange support via CCXT | ✅ Active |
| `models.py` | ~670 | SQLAlchemy database models with optimized indexes | ✅ Active |
| `routers.py` | ~639 | FastAPI routers for user/admin exchange management | ✅ Active |
| `schemas.py` | ~285 | Pydantic schemas for API request/response validation | ✅ Active |
| `security.py` | ~856 | Security module (rate limiting, auth, encryption, audit logging) | ✅ Active |
| `config.py` | ~401 | Configuration management with Docker Secret support | ✅ Active |
| `telegram_notifier.py` | ~615 | Telegram and Email notification system | ✅ Active |
| `telegram_bot.py` | ~400 | Telegram bot with OTP-protected panic kill switch | ✅ Active |
| `smart_features.py` | ~1112 | Trailing Stop-Loss, DCA, and Risk Guardrails | ✅ Active |
| `payment_router.py` | ~572 | Plisio crypto payment gateway integration | ✅ Active |
| `service_validator.py` | ~300 | Exchange credential validation via CCXT | ✅ Active |
| `metrics.py` | ~400 | Prometheus metrics collection | ✅ Active |
| `worker.py` | ~470 | ARQ background worker for async task processing | ✅ Active |
| `tasks.py` | ~577 | Background task definitions (signals, subscriptions, DCA) | ✅ Active |
| `run_server.py` | ~70 | Production server launcher (Waitress on Windows) | ✅ Active |

### Utility Scripts

| File | Purpose | When to Use |
|------|---------|-------------|
| `setup_env.py` | Generate `.env` file with security keys | Initial setup |
| `validate_settings.py` | Validate `admin_settings.ini` and generate configs | Configuration check |
| `stress_test.py` | Load testing with simulated users | Performance testing |
| `optimize_assets.py` | Minify CSS/JS files | Before production deployment |
| `add_performance_indexes.py` | Add database performance indexes | After migrations |

### Migration Scripts

| File | Purpose |
|------|---------|
| `migrate_all.py` | Run all migrations in sequence |
| `migrate_add_columns.py` | Add new columns to existing tables |
| `migrate_add_smart_features.py` | Add DCA and Trailing SL columns |
| `migrate_add_risk_guardrails.py` | Add risk guardrails columns |
| `migrate_add_subscription.py` | Add subscription and payment tables |
| `migrate_sqlite_to_postgres.py` | Migrate data from SQLite to PostgreSQL |

### Batch/Shell Scripts

| File | Platform | Purpose |
|------|----------|---------|
| `SETUP_AND_START.bat` / `setup_and_start.sh` | Windows/Linux | One-click setup and start |
| `START.bat` / `start.sh` | Windows/Linux | Interactive start menu |
| `START_PRODUCTION.bat` | Windows | Quick production start |
| `CONFIGURE.bat` / `configure.sh` | Windows/Linux | Configuration helper |
| `deploy_production.bat` / `.ps1` | Windows | Production deployment |
| `run_bot.bat` | Windows | Development mode launcher |
| `run_production.bat` / `.sh` | Windows/Linux | Production mode |
| `run_worker.bat` | Windows | Start ARQ worker |
| `fix_port.bat` | Windows | Free port 80 from conflicts |
| `backup_db.sh` | Linux/Mac | PostgreSQL backup with S3/GDrive upload |

### Template Files

| File | Purpose | Auth Required |
|------|---------|---------------|
| `base.html` | Base layout with navbar, sidebar, footer | - |
| `index.html` | Landing page with features showcase | No |
| `login.html` | User authentication form | No |
| `register.html` | Registration with referral code support | No |
| `dashboard_admin.html` | Admin control panel | Admin |
| `dashboard_user.html` | User trading dashboard | User |
| `leaderboard.html` | Public trading leaderboard | No |
| `messages_user.html` | User inbox | User |
| `messages_admin.html` | Admin inbox with all users | Admin |
| `message_view_user.html` | Single message thread view | User |
| `message_view_admin.html` | Admin message thread view | Admin |
| `forgot_password.html` | Password reset request form | No |
| `reset_password.html` | Password reset with code verification | No |
| `change_password.html` | Change password form | User |

### Static Assets

| Directory/File | Purpose |
|----------------|---------|
| `static/css/main.css` | Main stylesheet (~4400 lines) |
| `static/css/main.min.css` | Minified CSS for production |
| `static/js/main.js` | Main JavaScript (~1750 lines) |
| `static/js/main.min.js` | Minified JS for production |
| `static/avatars/` | User uploaded avatar images |
| `static/manifest.json` | PWA manifest |
| `static/mimic-logo.svg` | Application logo |
| `static/og-image.svg` | Social media preview image |
| `static/robots.txt` | SEO robots file |
| `static/sitemap.xml` | SEO sitemap |

### Configuration Files

| File | Purpose | Commit to Git? |
|------|---------|----------------|
| `.env` | Secret keys and credentials | ❌ NO |
| `config.ini` | Runtime configuration | ❌ NO |
| `config.ini.example` | Configuration template | ✅ YES |
| `admin_settings.ini` | Comprehensive admin settings | ❌ NO (contains secrets) |
| `production.env.example` | Production environment template | ✅ YES |
| `docker.env.example` | Docker environment template | ✅ YES |
| `docker-compose.yml` | Full Docker stack definition | ✅ YES |
| `Dockerfile` | Container build instructions | ✅ YES |
| `nginx.conf.example` | Nginx reverse proxy config | ✅ YES |
| `requirements.txt` | Python dependencies | ✅ YES |

---

## 📞 Support

For issues and questions:
1. Check this documentation first
2. Review application logs
3. Check GitHub issues
4. Contact the development team

---

**⚠️ DISCLAIMER**: Cryptocurrency trading involves significant risk. Use this software at your own risk. The developers are not responsible for any financial losses.

---

*Last updated: January 6, 2026*  
*Code Audit: Cursor AI*
