# 🧠 MIMIC (Brain Capital)

**Automated Copy Trading Platform for Cryptocurrency Exchanges**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-3.0-green.svg)](https://flask.palletsprojects.com/)
[![FastAPI](https://img.shields.io/badge/fastapi-0.104-teal.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A platform that enables users to automatically copy trades from a master account across multiple cryptocurrency exchanges via TradingView webhooks.

---

## ✨ Key Features

- 🔄 **Automatic Copy Trading** - Users automatically copy master account trades
- 📊 **TradingView Webhooks** - Integration with TradingView alerts
- 🔐 **Encrypted API Keys** - Secure storage using Fernet encryption
- 📱 **Telegram Notifications** - Real-time trade alerts
- 📈 **Real-time Dashboard** - Live position monitoring via WebSockets
- 🌐 **30+ Exchanges** - Multi-exchange support via CCXT
- 🛡️ **Risk Controls** - Configurable risk, leverage, TP/SL settings
- 🚨 **Emergency Kill Switch** - 2FA protected panic close via Telegram
- 💳 **Subscription System** - Crypto payments via Plisio
- 📉 **Smart Features** - Trailing Stop-Loss, DCA, Risk Guardrails

---

## 🚀 Quick Start (One-Click Setup)

### Windows (Recommended)

**Double-click `SETUP_AND_START.bat`** to automatically:
1. ✅ Check Python installation
2. ✅ Install all dependencies
3. ✅ Generate security keys
4. ✅ Create configuration files
5. ✅ Run database migrations
6. ✅ Start the application

```batch
# Or run from command prompt:
SETUP_AND_START.bat
```

### Linux / macOS

```bash
# Make script executable
chmod +x setup_and_start.sh

# Run the setup and start script
./setup_and_start.sh

# For production mode:
./setup_and_start.sh --production
```

### Access the Application

Open: **http://localhost** (or **http://localhost:5000** for development)

**Default login:** `admin` / `admin`

> ⚠️ **Change the default password immediately!**

---

## 📋 Complete Installation Guide

### Prerequisites

- **Python 3.10+** (3.13 recommended) - [Download](https://www.python.org/downloads/)
- **Git** (optional) - [Download](https://git-scm.com/downloads)
- **(Optional)** Redis for task queue
- **(Optional)** PostgreSQL for production
- **(Optional)** Docker for containerized deployment

### Step-by-Step Manual Installation

#### Step 1: Download and Navigate

```bash
# Option A: Clone with Git
git clone <repository-url>
cd "MIMIC v3.0"

# Option B: Download ZIP and extract
cd "MIMIC v3.0"
```

#### Step 2: Install Dependencies

```bash
# Windows
pip install -r requirements.txt

# Linux/macOS (with virtual environment)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### Step 3: Generate Security Keys

```bash
# Generates .env file with secure encryption keys
python setup_env.py

# To regenerate (warning: will invalidate encrypted data)
python setup_env.py --force
```

#### Step 4: Configure the Application

```bash
# Windows
copy config.ini.example config.ini

# Linux/macOS
cp config.ini.example config.ini
```

Edit `config.ini` with your settings:
```ini
[binance]
api_key = your_binance_api_key
api_secret = your_binance_api_secret

[telegram]
bot_token = your_telegram_bot_token
chat_id = your_telegram_chat_id

[trading]
risk_perc = 3
leverage = 20
tp_perc = 5
sl_perc = 2
```

#### Step 5: Run Database Migrations (if upgrading)

```bash
# Run all database migrations
python migrate_all.py

# Or run individual migrations:
python migrate_add_columns.py
python migrate_add_smart_features.py
python migrate_add_risk_guardrails.py
python migrate_add_subscription.py
```

#### Step 6: Start the Application

```bash
# Development Mode (port 5000)
python app.py

# Production Mode (port 80, requires Administrator/root)
python run_server.py
```

---

## 🐳 Docker Deployment

### Quick Start with Docker

```bash
# Copy environment file
cp docker.env.example .env

# Edit .env with your configuration
nano .env

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Docker Services

| Service | Port | Description |
|---------|------|-------------|
| app | 80 | Main application |
| redis | 6379 | Cache & task queue |
| postgres | 5432 | Database |
| prometheus | 9090 | Metrics |
| grafana | 3000 | Dashboards |

---

## 📡 TradingView Webhook Setup

### Webhook URL
```
http://YOUR_SERVER_IP/webhook
```

### JSON Alert Format
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

### Supported Actions

| Action | Description |
|--------|-------------|
| `long` | Open LONG position |
| `short` | Open SHORT position |
| `close` | Close position by symbol |

---

## 🔐 Security

### API Key Configuration (Binance)

1. ✅ Enable `Futures Trading`
2. ❌ **Disable** `Enable Withdrawals`
3. ✅ Enable `Restrict access to trusted IPs only`
4. ⚠️ Store Secret Key securely

### Files to NEVER Commit

- `.env` - Secret keys
- `config.ini` - API keys and settings
- `*.db` - Database files
- `secrets/` - Encryption keys

---

## 📁 Project Structure

```
MIMIC v3.0/
├── 🚀 Entry Points
│   ├── SETUP_AND_START.bat   # Windows one-click setup
│   ├── setup_and_start.sh    # Linux/Mac one-click setup
│   ├── app.py                # Main Flask application (4300+ lines)
│   └── run_server.py         # Production server launcher
│
├── 🔧 Core Modules
│   ├── app_fastapi.py        # FastAPI for exchanges/payments
│   ├── trading_engine.py     # Copy trading engine (CCXT)
│   ├── config.py             # Configuration management
│   ├── models.py             # Database models (SQLAlchemy)
│   ├── security.py           # Security & rate limiting
│   ├── smart_features.py     # Trailing SL, DCA, Risk Guardrails
│   ├── routers.py            # FastAPI exchange routers
│   ├── schemas.py            # Pydantic validation schemas
│   └── payment_router.py     # Plisio crypto payments
│
├── 📡 Communications
│   ├── telegram_notifier.py  # Telegram + Email notifications
│   └── telegram_bot.py       # Telegram bot with OTP kill switch
│
├── 🔄 Background Processing
│   ├── worker.py             # ARQ async worker
│   └── tasks.py              # Background task definitions
│
├── 🗄️ Database Migrations
│   ├── migrate_all.py        # Run all migrations
│   └── migrate_*.py          # Individual migration scripts
│
├── 🎨 Frontend
│   ├── templates/            # Jinja2 HTML templates (14 files)
│   └── static/               # CSS, JS, images, manifest
│
├── 📊 Monitoring
│   └── monitoring/           # Prometheus, Grafana, Loki configs
│
├── 🐳 Docker
│   ├── docker-compose.yml    # Full production stack
│   ├── Dockerfile            # Container build
│   └── docker/init-db/       # PostgreSQL initialization
│
└── 📚 Documentation
    ├── README.md             # This file
    ├── DEV_MANUAL.md         # Complete developer manual
    ├── SECURITY.md           # Security guidelines
    └── SECURITY_HARDENING.md # Production hardening
```

📚 **For complete documentation, see [DEV_MANUAL.md](DEV_MANUAL.md)**

---

## 🧑‍💻 Developer Quick Start

### First Time Setup (5 minutes)

```bash
# 1. Clone and enter directory
git clone <repository-url>
cd "MIMIC v3.0"

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Generate security keys
python setup_env.py

# 5. Copy and edit configuration
copy config.ini.example config.ini
# Edit config.ini with your API keys

# 6. Start development server
python app.py
```

### Key Files for Developers

| If you need to... | Look at... |
|-------------------|------------|
| Add a new API endpoint | `app.py` (Flask) or `routers.py` (FastAPI) |
| Add a database model | `models.py` + create migration |
| Modify trading logic | `trading_engine.py` |
| Change frontend UI | `templates/` + `static/css/main.css` |
| Add JavaScript | `static/js/main.js` |
| Configure settings | `config.py` |
| Add background tasks | `tasks.py` + `worker.py` |

### Code Style

- Python: Follow PEP 8
- Use type hints where possible
- Logging: `✅` success, `❌` error, `⚠️` warning, `🔄` processing
- Comments in English, UI text supports Ukrainian/English

---

## 🛠️ Configuration

### Global Trading Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `risk_perc` | Risk percentage per trade | 3% |
| `leverage` | Leverage multiplier | 20x |
| `tp_perc` | Take Profit percentage | 5% |
| `sl_perc` | Stop Loss percentage | 2% |
| `max_positions` | Maximum open positions | 10 |

### Environment Variables

| Variable | Description |
|----------|-------------|
| `FLASK_SECRET_KEY` | Flask session secret (required) |
| `BRAIN_CAPITAL_MASTER_KEY` | Fernet encryption key (required) |
| `DATABASE_URL` | PostgreSQL URL (optional) |
| `REDIS_URL` | Redis URL (optional) |
| `PLISIO_API_KEY` | Payment gateway key (optional) |

---

## 📱 Telegram Notifications

The bot sends alerts for:
- 📥 New signals received
- ✅ Trades opened
- 💰 Trades closed with PnL
- ⚠️ Errors
- 🚨 Emergency closures

### Panic Kill Switch

Use Telegram with OTP to close all positions:
```
/panic <OTP_CODE>
```

---

## 🐛 Troubleshooting

### Database Migration Error
```
sqlite3.OperationalError: no such column: users.risk_multiplier
```
**Solution:** Run the migration script:
```bash
python migrate_all.py
```

### Port 80 in Use
```bash
# Windows - Run fix_port.bat or:
netstat -ano | findstr :80
taskkill /PID <pid> /F
```

### Encryption Error
```bash
python setup_env.py --force
```

### Fresh Database Start
```bash
# Delete existing database and restart
del brain_capital.db    # Windows
rm brain_capital.db     # Linux/Mac
python app.py           # Creates new database
```

---

## 🚢 Production Deployment

### Windows (as Administrator)
```batch
# One-click production setup
SETUP_AND_START.bat

# Or manually:
python run_server.py
```

### Linux (with systemd)
```bash
# Setup
./setup_and_start.sh --production

# Or with gunicorn:
gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker \
         -w 4 -b 0.0.0.0:80 app:app
```

### Docker (Recommended for Production)
```bash
docker-compose up -d
```

📚 **See [DEV_MANUAL.md](DEV_MANUAL.md) for complete deployment guide**

---

## 💳 Subscription System

Built-in crypto payment support via Plisio:

| Plan | Price | Features |
|------|-------|----------|
| Basic | $29.99/mo | 3 exchanges, email support |
| Pro | $79.99/mo | 10 exchanges, priority support, analytics |
| Enterprise | $199.99/mo | Unlimited exchanges, API access |

Supported currencies: USDT (TRC20/ERC20), BTC, ETH, LTC

---

## 📈 Monitoring

Docker Compose includes:
- **Prometheus** - Metrics collection
- **Grafana** - Dashboards (port 3000)
- **Loki** - Log aggregation

Pre-configured dashboards for:
- Trading metrics
- Admin PnL overview
- System health

---

## 📄 License

MIT License

---

## 🤝 Contributing

1. Check [DEV_MANUAL.md](DEV_MANUAL.md) for architecture overview
2. Create an issue for bugs or feature requests
3. Submit pull requests with tests

---

## 📞 Support

- Check [DEV_MANUAL.md](DEV_MANUAL.md) for troubleshooting
- Review application logs
- Create GitHub issues

---

**⚠️ DISCLAIMER**: Cryptocurrency trading involves significant risk. Use this software at your own risk. The developers are not responsible for any financial losses.
