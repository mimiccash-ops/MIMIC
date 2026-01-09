# 🧠 MIMIC (Brain Capital) - Developer Manual

**Copy Trading Platform for Cryptocurrency Exchanges**

Version: 3.1  
Last Updated: January 9, 2026  
Code Audit Date: January 9, 2026

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
15. [Service Connections](#-service-connections)

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
| 🏆 **Gamification** | XP, Levels, Achievements, and Tournaments |
| 🗳️ **Governance** | Elite user voting on platform proposals |
| 💬 **Live Chat** | Real-time chat with other traders |
| 🤖 **AI Support Bot** | RAG-based support using OpenAI |
| 📊 **Influencer Dashboard** | Referral analytics and banner generation |
| 📱 **PWA Support** | Progressive Web App with push notifications |

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
│  │  ├─ /leaderboard  → Trading leaderboard                        ││
│  │  ├─ /tournament   → Tournament system                          ││
│  │  ├─ /governance   → Elite user voting                          ││
│  │  ├─ /influencer   → Influencer analytics                       ││
│  │  └─ /api/*        → REST API endpoints                         ││
│  └─────────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    FastAPI (app_fastapi.py)                     ││
│  │  ├─ /user/exchanges/*   → User exchange management             ││
│  │  ├─ /admin/exchanges/*  → Admin approval workflow              ││
│  │  ├─ /api/payment/*      → Subscription payments                ││
│  │  └─ /api/public/*       → Public Developer API                 ││
│  └─────────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                      Flask-SocketIO                             ││
│  │  └─ Real-time updates (balance, positions, trades, chat)       ││
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
│           │                                                         │
│  ┌────────▼────────┐  ┌────────────────┐  ┌──────────────────────┐ │
│  │ Support Bot     │  │ Compliance     │  │ Sentiment Analysis   │ │
│  │ (RAG + OpenAI)  │  │ (Geo-blocking) │  │ (Fear/Greed)         │ │
│  └─────────────────┘  └────────────────┘  └──────────────────────┘ │
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
| **AI Support** | OpenAI + LangChain | RAG-based support bot |

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
cd MIMIC

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
copy config.ini.example config.ini  # Windows
cp config.ini.example config.ini    # Linux/Mac

# Edit config.ini with your Binance API keys and settings
```

### 3. Run Database Migrations

```bash
# Run all database migrations
python migrate_all.py
```

### 4. Start the Application

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
```

### 5. Access the Application

- **Local**: http://localhost (or http://localhost:5000)
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
| `OPENAI_API_KEY` | OpenAI API key for support bot | None |
| `VAPID_PUBLIC_KEY` | Web push public key | None |
| `VAPID_PRIVATE_KEY` | Web push private key | None |

### Generate Security Keys

```python
# Generate FLASK_SECRET_KEY
import secrets
print(secrets.token_hex(32))

# Generate BRAIN_CAPITAL_MASTER_KEY (Fernet)
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

---

## 📁 Project Structure

```
MIMIC/
│
├── 📄 Core Application
│   ├── app.py                    # Main Flask application (~7900 lines)
│   ├── app_fastapi.py            # FastAPI for exchange/payment management
│   ├── config.py                 # Configuration with env validation
│   ├── models.py                 # SQLAlchemy database models (~700 lines)
│   ├── routers.py                # FastAPI routers (user/admin exchanges)
│   ├── schemas.py                # Pydantic schemas for FastAPI
│   ├── security.py               # Security module (rate limiting, auth)
│   ├── trading_engine.py         # Copy trading engine (~3800 lines)
│   ├── telegram_notifier.py      # Telegram & Email notifications
│   ├── telegram_bot.py           # Telegram bot with OTP kill switch
│   ├── service_validator.py      # Exchange validation via CCXT
│   ├── payment_router.py         # Plisio crypto payment integration
│   ├── smart_features.py         # Trailing SL, DCA, Risk Guardrails
│   ├── public_api.py             # Public Developer API
│   ├── compliance.py             # Geo-blocking and TOS consent
│   ├── sentiment.py              # Fear & Greed sentiment analysis
│   ├── support_bot.py            # RAG support bot (OpenAI + LangChain)
│   ├── banner_generator.py       # Influencer banner generation
│   ├── post_to_twitter.py        # Twitter/X auto-posting
│   ├── metrics.py                # Prometheus metrics
│   └── run_server.py             # Production server launcher
│
├── 📄 Background Tasks (Optional)
│   ├── worker.py                 # ARQ worker for async tasks
│   └── tasks.py                  # Task definitions
│
├── 📄 Configuration
│   ├── config.ini                # Runtime config (DO NOT COMMIT)
│   ├── config.ini.example        # Configuration template
│   ├── .env                      # Environment secrets (DO NOT COMMIT)
│   ├── production.env.example    # Production env template
│   └── requirements.txt          # Python dependencies
│
├── 📄 Utilities & Scripts
│   ├── setup_env.py              # Generate .env file
│   ├── validate_settings.py      # Validate config files
│   ├── stress_test.py            # Load testing
│   ├── optimize_assets.py        # JS/CSS minification
│   ├── add_performance_indexes.py # Database optimization
│   ├── generate_vapid_keys.py    # Generate VAPID keys for web push
│   ├── generate_pwa_icons.py     # Generate PWA icons
│   └── ingest_docs.py            # RAG document ingestion
│
├── 📄 Migration Scripts
│   ├── migrate_all.py            # Run all migrations in sequence
│   ├── migrate_add_columns.py    # Basic column additions
│   ├── migrate_add_smart_features.py # DCA and Trailing SL
│   ├── migrate_add_risk_guardrails.py # Risk guardrails
│   ├── migrate_add_subscription.py # Subscription system
│   ├── migrate_add_strategies.py # Multi-strategy support
│   ├── migrate_add_chat.py       # Live chat system
│   ├── migrate_add_gamification.py # Levels & achievements
│   ├── migrate_add_governance.py # Voting/proposals
│   ├── migrate_add_tournaments.py # Tournament system
│   ├── migrate_add_api_keys.py   # Public API keys
│   ├── migrate_add_compliance.py # TOS consent tracking
│   ├── migrate_add_influencer.py # Influencer analytics
│   ├── migrate_add_support_bot.py # RAG support tables
│   ├── migrate_add_insurance_fund.py # Insurance fund
│   ├── migrate_add_push_subscriptions.py # Web push
│   ├── migrate_high_traffic_indexes.py # Performance indexes
│   └── migrate_sqlite_to_postgres.py # DB migration
│
├── 📄 Deployment
│   ├── SETUP_AND_START.bat       # Windows one-click setup
│   ├── setup_and_start.sh        # Linux one-click setup
│   ├── START.bat / start.sh      # Interactive menu
│   ├── DEPLOY.bat / deploy.sh    # VPS deployment scripts
│   ├── deploy_production.bat     # Windows production deployment
│   ├── deploy_production.ps1     # PowerShell deployment
│   ├── run_production.bat/.sh    # Production mode launcher
│   ├── run_bot.bat               # Development mode launcher
│   ├── run_worker.bat            # Start ARQ worker
│   ├── fix_port.bat              # Free port 80 conflicts
│   ├── vps_setup.sh              # One-time VPS setup
│   ├── mimic.service             # Systemd service template
│   ├── Dockerfile                # Docker container
│   ├── docker-compose.yml        # Full Docker stack
│   └── nginx.conf.production     # Production nginx config
│
├── 📂 static/                    # Static assets
│   ├── css/
│   │   ├── main.css              # Main stylesheet
│   │   ├── main.min.css          # Minified CSS
│   │   └── chat.css              # Live chat styles
│   ├── js/
│   │   ├── main.js               # Main JavaScript
│   │   ├── main.min.js           # Minified JS
│   │   ├── chat.js               # Live chat functionality
│   │   └── push.js               # Web push notifications
│   ├── icons/                    # PWA icons
│   ├── music/                    # Optional background music
│   ├── manifest.json             # PWA manifest
│   ├── service-worker.js         # PWA service worker
│   ├── mimic-logo.svg            # Logo
│   ├── og-image.svg              # Social media preview
│   ├── robots.txt                # SEO
│   └── sitemap.xml               # SEO
│
├── 📂 templates/                 # Jinja2 HTML templates (21 files)
│   ├── base.html                 # Base layout
│   ├── index.html                # Landing page
│   ├── login.html                # Login
│   ├── register.html             # Registration
│   ├── dashboard_admin.html      # Admin dashboard
│   ├── dashboard_user.html       # User dashboard
│   ├── leaderboard.html          # Trading leaderboard
│   ├── tournament.html           # Tournaments
│   ├── governance.html           # Voting/Proposals
│   ├── influencer.html           # Influencer analytics
│   ├── api_keys.html             # API key management
│   ├── messages_*.html           # Messaging system
│   ├── legal_*.html              # Legal pages (TOS, Privacy, Risk)
│   └── offline.html              # PWA offline page
│
├── 📂 monitoring/                # Observability stack
│   ├── grafana/                  # Grafana dashboards
│   ├── prometheus/               # Metrics and alerts
│   ├── loki/                     # Log aggregation
│   └── promtail/                 # Log shipping
│
├── 📂 .github/workflows/         # GitHub Actions
│   └── deploy.yml                # Auto-deploy to VPS
│
└── 📄 Documentation
    ├── README.md                 # Project overview
    ├── DEV_MANUAL.md             # This file
    ├── LINUX_DEPLOYMENT.md       # Linux deployment guide
    ├── SECURITY.md               # Security guidelines
    ├── SECURITY_HARDENING.md     # Production hardening
    ├── CLOUDFLARE_SETUP.md       # Cloudflare configuration
    ├── PUBLIC_API.md             # Public API documentation
    └── FAQ.md                    # Frequently Asked Questions
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
- Live chat system
- Tournament management
- Governance voting

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
- `Strategy` - Multi-strategy support
- `ChatMessage` / `ChatBan` - Live chat
- `UserLevel` / `UserAchievement` - Gamification
- `Tournament` / `TournamentParticipant` - Tournaments
- `Proposal` / `Vote` - Governance
- `ApiKey` - Public API keys
- `UserConsent` - TOS consent tracking

### `support_bot.py` - AI Support Bot

RAG-based support using OpenAI:
- Document ingestion and embedding
- Context-aware responses
- Confidence scoring
- Escalation to human support

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
| `/api/positions` | GET | Yes | Open positions |
| `/api/trades` | GET | Yes | Trade history |
| `/leaderboard` | GET | No | Public leaderboard |
| `/tournament` | GET | Yes | Tournament page |
| `/governance` | GET | Yes | Voting proposals |
| `/influencer` | GET | Yes | Influencer dashboard |
| `/api-keys` | GET | Yes | API key management |

### FastAPI Routes (app_fastapi.py)

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | No | Health check |
| `/user/exchanges/` | GET | Bearer | List user's exchanges |
| `/user/exchanges/` | POST | Bearer | Add new exchange |
| `/admin/exchanges/pending` | GET | Admin | List pending approvals |
| `/api/payment/plans` | GET | No | Get subscription plans |
| `/api/payment/create` | POST | Bearer | Create payment invoice |
| `/api/public/*` | GET | API Key | Public Developer API |

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

| Table | Description |
|-------|-------------|
| `users` | User accounts with settings |
| `trade_history` | Trade records with PnL |
| `balance_history` | Balance snapshots |
| `user_exchanges` | Multi-exchange connections |
| `exchange_configs` | Admin exchange configuration |
| `messages` | Internal messaging |
| `referral_commissions` | Referral tracking |
| `referral_clicks` | Influencer click tracking |
| `payout_requests` | Influencer payouts |
| `payments` | Subscription payments |
| `strategies` | Multi-strategy support |
| `strategy_subscriptions` | User strategy subscriptions |
| `chat_messages` | Live chat messages |
| `chat_bans` | Chat moderation |
| `user_levels` | Gamification levels |
| `user_achievements` | User badges |
| `tournaments` | Tournament definitions |
| `tournament_participants` | Tournament entries |
| `proposals` | Governance proposals |
| `votes` | User votes |
| `api_keys` | Public API keys |
| `user_consents` | TOS consent records |
| `document_chunks` | RAG document storage |
| `support_conversations` | Support chat sessions |
| `support_messages` | Support chat messages |
| `support_tickets` | Escalated tickets |
| `system_stats` | Insurance fund, etc. |

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
| **Geo-blocking** | GeoIP-based jurisdiction blocking |
| **TOS Consent** | Version-tracked consent records |

---

## 📋 Technical Debt & TODOs

### Code Audit Summary (January 9, 2026)

**Audit Scope:** Full codebase review including backend, frontend, configuration, and deployment scripts.

#### Active TODO Comments in Code

**Total active TODOs found:** 0

All previously identified TODOs have been implemented:

| File | Status | Description |
|------|--------|-------------|
| `smart_features.py` | ✅ **FIXED** | Trailing SL trigger now executes actual position close via exchange |
| `public_api.py` | ✅ **FIXED** | Public API position endpoint now fetches positions from exchanges |

#### Issues Found and Fixed

| Issue | Status | Date |
|-------|--------|------|
| Missing legal templates (`legal_tos.html`, `legal_privacy.html`, `legal_risk_disclaimer.html`) | ✅ **Created** | Jan 9, 2026 |

### Recommendations

#### 🔴 High Priority
1. ~~**Complete trailing SL execution**~~ - ✅ **DONE** (Jan 9, 2026)
2. ~~**Complete public API position fetching**~~ - ✅ **DONE** (Jan 9, 2026)
3. **Add comprehensive unit/integration tests** - No test suite exists
4. **Set up CI/CD pipeline** - GitHub Actions for automated testing

#### 🟡 Medium Priority
1. **Database migrations with Alembic** - Consider for version control
2. **Centralized logging with Loki** - Production tuning needed
3. **API documentation** - Add detailed docstrings
4. **WebSocket reconnection logic** - Improve client-side handling

#### 🟢 Low Priority
1. **User API rate limiting per subscription tier**
2. **Error tracking with Sentry**
3. **APM integration** - Application Performance Monitoring
4. **Image optimization** - WebP conversion

### All Files Are Actively Used

No unused files were found during the audit. All Python files, templates, and static assets are referenced and utilized.

---

## 🔌 Service Connections

### config.ini.example - All Service Sections

| Section | Service | Required |
|---------|---------|----------|
| `[MasterAccount]` | Binance API | ✅ Yes |
| `[Webhook]` | TradingView passphrase | ✅ Yes |
| `[Settings]` | Trading settings | ✅ Yes |
| `[Telegram]` | Telegram bot | ⚠️ Recommended |
| `[Email]` | SMTP email | Optional |
| `[Production]` | Domain & SSL | Production only |
| `[Proxy]` | Proxy rotation | High-volume only |
| `[PanicOTP]` | Kill switch 2FA | ⚠️ Recommended |
| `[WebPush]` | PWA notifications | Optional |
| `[Twitter]` | Auto-posting | Optional |
| `[Compliance]` | Geo-blocking & TOS | ⚠️ Recommended |
| `[SupportBot]` | OpenAI RAG bot | Optional |
| `[Payment]` | Plisio payments | Optional |

### Environment Variables (.env)

```bash
# Required
FLASK_SECRET_KEY=your-secret-key-here
BRAIN_CAPITAL_MASTER_KEY=your-fernet-key-here

# Database (optional - defaults to SQLite)
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Redis (optional - for task queue)
REDIS_URL=redis://localhost:6379/0

# Production settings
FLASK_ENV=production
PRODUCTION_DOMAIN=https://yourdomain.com
HTTPS_ENABLED=true

# Exchange API (can also be in config.ini)
BINANCE_MASTER_API_KEY=your-binance-api-key
BINANCE_MASTER_API_SECRET=your-binance-api-secret

# Telegram
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_CHAT_ID=your-telegram-chat-id

# Payments
PLISIO_API_KEY=your-plisio-api-key
PLISIO_WEBHOOK_SECRET=your-webhook-secret

# Support Bot
OPENAI_API_KEY=your-openai-api-key

# Web Push
VAPID_PUBLIC_KEY=your-vapid-public-key
VAPID_PRIVATE_KEY=your-vapid-private-key
```

---

## 🚢 Production Deployment

### One-Command VPS Deployment

#### From Windows (PowerShell)
```powershell
.\deploy.ps1
```

#### From Windows (Batch)
```batch
DEPLOY.bat
```

#### From Linux/Mac
```bash
./deploy.sh
```

### Initial VPS Setup

Run once on your VPS:
```bash
scp vps_setup.sh root@YOUR_VPS_IP:/tmp/
ssh root@YOUR_VPS_IP "chmod +x /tmp/vps_setup.sh && /tmp/vps_setup.sh"
```

### GitHub Actions Auto-Deploy

Push to `main` branch triggers automatic deployment. Configure secrets:
- `VPS_HOST` - Your VPS IP
- `VPS_USER` - SSH username
- `VPS_SSH_KEY` - Private SSH key
- `VPS_PORT` - SSH port (22)

### Docker Deployment

```bash
docker-compose up -d
```

---

## 🔧 Troubleshooting

### Common Issues

#### Port 80 Already in Use
```batch
# Windows
fix_port.bat
```

#### Encryption Error
```bash
python setup_env.py --force
```

#### Database Migration Error
```bash
python migrate_all.py
```

#### WebSocket Connection Failed
- Check firewall allows WebSocket traffic
- Verify nginx proxy configuration
- Check CORS settings

---

## 💻 Development Workflow

### Code Style

- Follow PEP 8 guidelines
- Use type hints where possible
- Document functions with docstrings
- Use logging instead of print statements
- Emojis in log messages: ✅ success, ❌ error, ⚠️ warning, 🔄 processing

### Testing Webhook

```bash
curl -X POST http://localhost/webhook \
  -H "Content-Type: application/json" \
  -d '{"passphrase":"your_passphrase","symbol":"BTCUSDT","action":"long"}'
```

### Database Migrations

When changing models:
1. Update `models.py`
2. Add changes to `migrate_all.py` or create new migration script
3. Run migration: `python migrate_all.py`

---

## 📞 Support

For issues and questions:
1. Check this documentation first
2. Review application logs
3. Check GitHub issues
4. Use the internal messaging system

---

**⚠️ DISCLAIMER**: Cryptocurrency trading involves significant risk. Use this software at your own risk. The developers are not responsible for any financial losses.

---

*Last updated: January 9, 2026*  
*Code Audit: Full codebase review - 2 active TODOs found, 3 missing templates created*
