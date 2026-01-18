# 🧠 MIMIC (Brain Capital) - Developer Manual

Version: 4.0  
Last Updated: January 18, 2026  
Code Audit Date: January 18, 2026

---

## 📑 Table of Contents

1. [Project Overview](#-project-overview)
2. [Architecture](#-architecture)
3. [Quick Start (Scripts)](#-quick-start-scripts)
4. [Manual Setup](#-manual-setup)
5. [Running Services](#-running-services)
6. [Docker Deployment](#-docker-deployment)
7. [Configuration Reference](#-configuration-reference)
8. [Frontend Assets](#-frontend-assets)
9. [Database & Migrations](#-database--migrations)
10. [Background Tasks (ARQ)](#-background-tasks-arq)
11. [Observability](#-observability)
12. [Testing](#-testing)
13. [Security Features](#-security-features)
14. [Deployment Notes](#-deployment-notes)
15. [Code Audit & Technical Debt](#-code-audit--technical-debt)
16. [Functional Verification Checklist](#-functional-verification-checklist)
17. [Utility Scripts Reference](#-utility-scripts-reference)
18. [Support](#-support)

---

## 🎯 Project Overview

**MIMIC (Brain Capital)** is a professional copy-trading platform that:
- Receives TradingView signals via webhook
- Mirrors trades across connected exchange accounts (30+ exchanges via CCXT)
- Provides user management, risk controls, and real-time dashboards
- Includes Telegram notifications, AI support bot, and gamification features

---

## 🏗 Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        MIMIC Platform                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │   app.py    │    │  worker.py  │    │ run_bot.py  │         │
│  │  (Flask +   │    │   (ARQ +    │    │ (Telegram   │         │
│  │ Socket.IO)  │    │   Redis)    │    │   Bot)      │         │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘         │
│         │                  │                  │                 │
│         └────────┬─────────┴─────────┬────────┘                 │
│                  │                   │                          │
│  ┌───────────────▼───────────────────▼──────────────────┐      │
│  │            trading_engine.py                          │      │
│  │     (Copy Trading Logic + Exchange Adapters)          │      │
│  └───────────────────────────────────────────────────────┘      │
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │  models.py  │    │ security.py │    │  config.py  │         │
│  │ (Database)  │    │ (Auth/CSRF) │    │  (Config)   │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### File Structure

```
MIMIC/
├── app.py                  # Main Flask app + Socket.IO + Routes (~10,880 lines)
├── trading_engine.py       # Copy trading engine + CCXT (~4,700 lines)
├── worker.py               # ARQ worker for background tasks (~605 lines)
├── tasks.py                # Background task definitions (~1,575 lines)
├── run_bot.py              # Telegram bot runner (standalone)
├── config.py               # Configuration loader (~595 lines)
├── models.py               # SQLAlchemy models (~4,340 lines)
├── security.py             # Security utilities (~990 lines)
│
├── telegram_notifier.py    # Telegram notifications + Email sender
├── telegram_bot.py         # Telegram bot commands + kill switch
├── support_bot.py          # RAG AI support bot (OpenAI)
├── sentiment.py            # AI sentiment analysis
├── smart_features.py       # Trailing SL, DCA, Risk Guardrails
├── compliance.py           # Geo-blocking + TOS consent
├── banner_generator.py     # Referral banner generation (Pillow)
├── post_to_twitter.py      # Twitter auto-posting for trades
├── metrics.py              # Prometheus metrics
├── sentry_config.py        # Sentry error tracking
├── service_validator.py    # Exchange validation
│
├── templates/              # Jinja2 HTML templates (26 files)
├── static/                 # CSS/JS/images
│   ├── css/
│   │   ├── main.min.css    # Minified main styles
│   │   ├── tailwind.css    # Compiled Tailwind
│   │   └── chat.css        # Chat widget styles
│   ├── js/
│   │   ├── main.min.js     # Minified main JS
│   │   ├── chat.js         # Chat WebSocket client
│   │   └── push.js         # PWA push notifications
│   └── icons/              # PWA icons
│
├── migrations/             # Database migrations
├── tests/                  # pytest test suite
├── monitoring/             # Prometheus/Grafana/Loki configs
├── logs/                   # Runtime logs (created automatically)
├── secrets/                # Local secrets (master.key)
│
├── config.ini              # Main configuration file
├── .env                    # Environment variables (not in git)
├── requirements.txt        # Python dependencies
├── package.json            # Frontend build scripts (Tailwind)
├── docker-compose.yml      # Docker orchestration
├── Dockerfile              # Container build
└── *.service               # Systemd unit files
```

---

## 🚀 Quick Start (Scripts)

### Windows

```batch
start_server.bat
```

### Linux / macOS

```bash
chmod +x start_server.sh
./start_server.sh
```

### Prerequisites

1. Copy `config.ini.example` to `config.ini` and configure API keys
2. Run `python setup_env.py` **or** copy `production.env.example` to `.env`
3. Ensure Redis is running (for worker)

The scripts automatically:
- Install Python/Node dependencies
- Build frontend CSS (Tailwind)
- Run database migrations
- Start `app.py`, `worker.py`, and optionally `run_bot.py`

---

## 📋 Manual Setup

### 1. Python Environment

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/macOS)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Node.js (Frontend Build)

```bash
npm install
```

### 3. Configuration Files

```bash
# Copy config templates
copy config.ini.example config.ini      # Windows
cp config.ini.example config.ini        # Linux/macOS

# Generate .env with secure keys
python setup_env.py

# Or manually copy and edit
copy production.env.example .env        # Windows
cp production.env.example .env          # Linux/macOS
```

### 4. Database Setup

```bash
python migrations/migrate.py
```

### 5. Build Frontend Assets

```bash
npm run build         # One-time build
npm run watch:css     # Development watcher
```

---

## 🧩 Running Services

### Web Application (Flask + Socket.IO)

```bash
python app.py
```

Default: `http://localhost:5000`

### Background Worker (ARQ + Redis)

```bash
python worker.py
```

**Requires Redis** at `REDIS_URL` (default: `redis://127.0.0.1:6379/0`)

### Telegram Bot (Standalone)

```bash
python run_bot.py
```

**Requires:** `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`

---

## 🐳 Docker Deployment

### Quick Start

```bash
# Copy environment file
cp docker.env.example .env    # Linux/macOS
copy docker.env.example .env  # Windows

# Create master key secret
mkdir -p secrets
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" > secrets/master.key

# Start all services
docker compose up -d
```

### Services Started

| Service | Port | Description |
|---------|------|-------------|
| `web` | 5000 | Flask web application |
| `worker` | 9091 | ARQ worker (Prometheus metrics) |
| `db` | 5432 | PostgreSQL 15 |
| `redis` | 6379 | Redis 7 |
| `prometheus` | 9090 | Metrics collection |
| `grafana` | 3000 | Dashboards |
| `loki` | 3100 | Log aggregation |
| `promtail` | - | Log shipping |

### Data Migration (SQLite → PostgreSQL)

```bash
docker compose --profile migration up migrate
```

---

## 🛠 Configuration Reference

### Environment Variables (`.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `FLASK_SECRET_KEY` | ✅ | Session encryption key (32+ chars) |
| `DATABASE_URL` | ❌ | PostgreSQL URL (defaults to SQLite) |
| `REDIS_URL` | ❌ | Redis URL for worker queue |
| `TELEGRAM_BOT_TOKEN` | ❌ | Telegram bot token |
| `TELEGRAM_CHAT_ID` | ❌ | Admin chat ID |
| `BINANCE_MASTER_API_KEY` | ❌ | Master account API key |
| `BINANCE_MASTER_API_SECRET` | ❌ | Master account API secret |
| `WEBHOOK_PASSPHRASE` | ❌ | TradingView webhook secret |
| `GOOGLE_CLIENT_ID` | ❌ | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | ❌ | Google OAuth secret |
| `WEBAUTHN_RP_ID` | ❌ | WebAuthn relying party ID |
| `OPENAI_API_KEY` | ❌ | OpenAI API key (support bot) |
| `SENTRY_DSN` | ❌ | Sentry error tracking DSN |

### Master Encryption Key

The master key for API key encryption is loaded in this order:

1. **Docker Secret:** `/run/secrets/brain_capital_master_key`
2. **Secure file:** `/etc/brain_capital/master.key`
3. **Local secrets:** `./secrets/master.key`
4. **Environment variable:** `BRAIN_CAPITAL_MASTER_KEY` (not recommended for production)

### config.ini Sections

| Section | Purpose |
|---------|---------|
| `[MasterAccount]` | Binance API credentials |
| `[Webhook]` | TradingView passphrase |
| `[Settings]` | Trading limits (testnet, max_positions) |
| `[Telegram]` | Bot token, chat ID, polling settings |
| `[Email]` | SMTP configuration |
| `[Proxy]` | Proxy rotation for high-volume |
| `[PanicOTP]` | Kill switch 2FA settings |
| `[WebPush]` | VAPID keys for PWA |
| `[Twitter]` | Auto-posting credentials |
| `[Compliance]` | Geo-blocking, TOS version |
| `[Payment]` | Plisio payment gateway |
| `[SupportBot]` | OpenAI/RAG configuration |

---

## 🎨 Frontend Assets

### CSS Architecture

- `main.min.css` - Minified main styles (production)
- `tailwind.css` - Compiled Tailwind CSS
- `chat.css` - Support chat widget styles

### JavaScript Architecture

- `main.min.js` - Minified main JS (production)
- `chat.js` - WebSocket chat client
- `push.js` - PWA push notifications

### Building CSS

```bash
# Production build (minified)
npm run build

# Development watch mode
npm run watch:css
```

---

## 💾 Database & Migrations

### Supported Databases

- **SQLite** (development) - Default, no configuration needed
- **PostgreSQL** (production) - Set `DATABASE_URL`

### Running Migrations

```bash
python migrations/migrate.py
```

### Key Models

| Model | Description |
|-------|-------------|
| `User` | User accounts with API keys, settings |
| `TradeHistory` | Executed trades log |
| `BalanceHistory` | Balance snapshots |
| `UserExchange` | Multi-exchange connections |
| `Payment` | Subscription payments |
| `Tournament` | Trading competitions |
| `UserLevel` | Gamification levels |
| `UserAchievement` | Unlocked badges |

---

## ⚙️ Background Tasks (ARQ)

### Task Queue

Tasks are queued via Redis and processed by `worker.py`:

| Task | Description |
|------|-------------|
| `execute_signal_task` | Process trading signals |
| `check_subscription_expiry_task` | Check/deactivate expired subscriptions |
| `execute_dca_check_task` | DCA order execution |
| `monitor_trailing_stops_task` | Trailing stop-loss monitoring |
| `update_market_sentiment_task` | AI sentiment updates |
| `calculate_user_xp_task` | Gamification XP calculation |
| `update_tournament_status_task` | Tournament lifecycle |

### Cron Jobs

| Schedule | Task |
|----------|------|
| Daily 9:00 UTC | Subscription expiry check |
| Daily 0:00 UTC | Reset daily balances (risk guardrails) |
| Daily 1:00 UTC | Calculate user XP |
| Every 5 minutes | DCA checks, tournament ROI |
| Every hour | Market sentiment update |
| Every minute | Tournament status updates |

---

## 📈 Observability

### Logging

- All logs in `logs/` directory
- `app.log` - Main application logs
- `worker.json` - Worker JSON logs (for Loki)
- `errors.log` - Error-only logs
- `critical.log` - Critical errors

### Prometheus Metrics

Exposed on port 9090 (Prometheus) and 9091 (worker):

- `trade_execution_latency_seconds`
- `active_positions_count`
- `failed_orders_total`
- `successful_orders_total`

### Grafana Dashboards

Pre-configured dashboards in `monitoring/grafana/dashboards/`:
- `admin-pnl.json` - PnL tracking
- `trading-metrics.json` - Trading metrics

---

## ✅ Testing

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=. --cov-report=html

# Run specific test file
pytest tests/test_trading.py -v
```

### Test Files

- `test_api.py` - API endpoint tests
- `test_models.py` - Database model tests
- `test_security.py` - Security feature tests
- `test_trading.py` - Trading engine tests

---

## 🔐 Security Features

### Authentication

- Password hashing (bcrypt)
- Google OAuth 2.0
- WebAuthn/Passkeys
- Session security (HTTP-only, SameSite cookies)

### API Security

- Rate limiting (per-IP, per-user)
- CSRF protection
- Input validation (Pydantic)
- XSS prevention (bleach)

### Trade Security

- API key encryption (Fernet)
- Webhook passphrase validation
- Panic kill switch with 2FA (TOTP)
- IP whitelisting for Binance

### Compliance

- Geo-blocking (GeoIP2)
- TOS consent tracking
- Audit logging

---

## 🚢 Deployment Notes

### Systemd Services

```bash
# Install services
sudo cp mimic.service /etc/systemd/system/
sudo cp mimic-worker.service /etc/systemd/system/
sudo cp mimic-bot.service /etc/systemd/system/

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable mimic mimic-worker mimic-bot
sudo systemctl start mimic mimic-worker mimic-bot
```

### Nginx Configuration

Use `nginx.conf.production` as a template for reverse proxy setup.

### SSL/HTTPS

1. **Recommended:** Use nginx as reverse proxy with Let's Encrypt
2. Set `HTTPS_ENABLED=true` in `.env`
3. Configure `PRODUCTION_DOMAIN` with your domain(s)

---

## 📋 Code Audit & Technical Debt

### Audit Summary (January 18, 2026)

**Scope:** Full codebase review including Python modules, templates, static assets, and scripts.

### TODO Comments Found

| File | Line | Content |
|------|------|---------|
| `templates/dashboard_admin.html` | 5140 | `// TODO: Implement edit functionality` |

### Technical Debt List

1. **Monolithic `app.py`** (~10,880 lines)
   - Contains routes, auth, webhooks, Socket.IO handlers
   - Recommendation: Split into Flask blueprints

2. **Large `trading_engine.py`** (~4,700 lines)
   - Complex async logic for multiple exchanges
   - Recommendation: More unit tests, consider splitting by exchange

3. **No frontend test suite**
   - UI regressions rely on manual testing
   - Recommendation: Add Playwright or Cypress tests

4. **Log file rotation**
   - File handlers write without rotation
   - Recommendation: Configure logrotate or use RotatingFileHandler

5. **Unused Alembic in requirements**
   - `alembic` is installed but not used (custom migrations)
   - Recommendation: Either adopt Alembic or remove from requirements

### Previous Cleanup (January 16, 2026)

The following were already removed per ARCHITECTURE_OPTIMIZATION_REPORT.md:
- `static/css/main.css` (kept `main.min.css`)
- `static/js/main.js` (kept `main.min.js`)
- `static/css/tailwind.input.css`
- `validate_settings.py`
- `configure.sh`

---

## 🔎 Functional Verification Checklist

Use this after changes to validate backend + frontend behavior:

### Startup

- [ ] `start_server.bat` / `start_server.sh` succeeds
- [ ] Migrations run without errors
- [ ] No critical errors in `logs/app.log`

### Web UI

- [ ] `/` - Landing page renders
- [ ] `/login` - Login form works
- [ ] `/register` - Registration with validation
- [ ] `/dashboard` - User dashboard loads
- [ ] `/admin` - Admin dashboard (admin user)

### API & Features

- [ ] POST `/webhook` - Valid payload returns success
- [ ] Socket.IO - Dashboard receives live updates
- [ ] `/api/keys` - API key management works
- [ ] `/api/exchanges` - Multi-exchange connections

### Background Services

- [ ] `worker.py` connects to Redis
- [ ] Tasks process correctly (check logs)
- [ ] `run_bot.py` polls Telegram successfully

### Frontend Build

- [ ] `npm run build` generates updated CSS
- [ ] No console errors in browser

---

## 🔧 Utility Scripts Reference

### Standalone Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `setup_env.py` | Generate `.env` with secure keys | `python setup_env.py` |
| `clear_pending.py` | Clear stuck symbols in Redis | `python clear_pending.py` |
| `check_outgoing_ip.py` | Verify outgoing IP for Binance | `python check_outgoing_ip.py` |
| `test_binance_keys.py` | Test Binance API permissions | `python test_binance_keys.py` |
| `ingest_docs.py` | Ingest docs for RAG support bot | `python ingest_docs.py` |
| `migrate_sqlite_to_postgres.py` | Migrate data to PostgreSQL | `python migrate_sqlite_to_postgres.py` |

### Shell Scripts

| Script | Purpose |
|--------|---------|
| `start_server.sh` | Start all services (Linux/macOS) |
| `start_server.bat` | Start all services (Windows) |
| `deploy.sh` | Deployment script |
| `deploy.ps1` | Windows deployment |
| `backup_db.sh` | Database backup |

---

## 📞 Support

1. **AI Support Bot:** Click chat icon in dashboard
2. **Logs:** Check `logs/` directory
3. **Documentation:**
   - `README.md` - Quick start guide
   - `FAQ.md` - Frequently asked questions
   - `SECURITY.md` - Security practices
   - `LINUX_DEPLOYMENT.md` - Linux deployment guide

---

**⚠️ DISCLAIMER:** Cryptocurrency trading involves significant risk. Use this software at your own risk. Past performance does not guarantee future results.
