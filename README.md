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
- 🏆 **Gamification** - XP, Levels, Achievements, Tournaments
- 💬 **Live Chat** - Real-time trader chat
- 🤖 **AI Support** - RAG-based support bot

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

## 📋 Manual Installation (5 Minutes)

### Prerequisites

- **Python 3.10+** (3.13 recommended) - [Download](https://www.python.org/downloads/)
- **Git** (optional) - [Download](https://git-scm.com/downloads)
- **(Optional)** Redis for task queue
- **(Optional)** PostgreSQL for production

### Step 1: Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd MIMIC

# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate      # Windows
source venv/bin/activate   # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Generate Security Keys

```bash
# Creates .env file with secure encryption keys
python setup_env.py
```

### Step 3: Configure the Application

```bash
# Windows
copy config.ini.example config.ini

# Linux/macOS
cp config.ini.example config.ini
```

Edit `config.ini` with your settings:
```ini
[MasterAccount]
api_key = your_binance_api_key
api_secret = your_binance_api_secret

[Webhook]
passphrase = your_secret_webhook_passphrase

[Telegram]
bot_token = your_telegram_bot_token
chat_id = your_telegram_chat_id
enabled = True
```

### Step 4: Run Database Migrations

```bash
python migrate_all.py
```

### Step 5: Start the Application

```bash
# Development Mode (port 5000)
python app.py

# Production Mode (port 80, requires Administrator/root)
python run_server.py
```

---

## 🐳 Docker Deployment

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
https://YOUR_DOMAIN/webhook
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

## 📁 Project Structure

```
MIMIC/
├── 🚀 Entry Points
│   ├── SETUP_AND_START.bat   # Windows one-click setup
│   ├── setup_and_start.sh    # Linux/Mac one-click setup
│   ├── app.py                # Main Flask application
│   ├── app_fastapi.py        # FastAPI endpoints
│   └── run_server.py         # Production server launcher
│
├── 🔧 Core Modules
│   ├── trading_engine.py     # Copy trading engine (CCXT)
│   ├── config.py             # Configuration management
│   ├── models.py             # Database models (SQLAlchemy)
│   ├── security.py           # Security & rate limiting
│   ├── smart_features.py     # Trailing SL, DCA, Risk Guardrails
│   └── payment_router.py     # Plisio crypto payments
│
├── 📡 Communications
│   ├── telegram_notifier.py  # Telegram + Email notifications
│   ├── telegram_bot.py       # Telegram bot with OTP kill switch
│   └── support_bot.py        # AI support bot (RAG + OpenAI)
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
│   ├── templates/            # Jinja2 HTML templates (21 files)
│   └── static/               # CSS, JS, images, PWA manifest
│
├── 📊 Monitoring
│   └── monitoring/           # Prometheus, Grafana, Loki configs
│
└── 📚 Documentation
    ├── README.md             # This file
    ├── DEV_MANUAL.md         # Complete developer manual (v3.2)
    ├── LINUX_DEPLOYMENT.md   # Linux server deployment
    ├── SECURITY.md           # Security guidelines
    ├── SECURITY_HARDENING.md # Production hardening
    ├── CLOUDFLARE_SETUP.md   # Cloudflare configuration
    ├── PUBLIC_API.md         # Public API documentation
    ├── AUTO_DEPLOY_SETUP.md  # Auto-deploy setup guide
    └── FAQ.md                # Frequently Asked Questions
```

📚 **For complete documentation, see [DEV_MANUAL.md](DEV_MANUAL.md)**

---

## 🧑‍💻 Developer Quick Start

### Key Files for Developers

| If you need to... | Look at... |
|-------------------|------------|
| Add a new API endpoint | `app.py` (Flask) or `routers.py` (FastAPI) |
| Add a database model | `models.py` + create migration script |
| Modify trading logic | `trading_engine.py` |
| Change frontend UI | `templates/` + `static/css/main.css` |
| Add JavaScript | `static/js/main.js` |
| Configure settings | `config.py` + `config.ini` |
| Add background tasks | `tasks.py` + `worker.py` |
| Add smart trading features | `smart_features.py` |
| Handle payments | `payment_router.py` |
| Add security features | `security.py` |
| Telegram notifications | `telegram_notifier.py` + `telegram_bot.py` |
| AI support bot | `support_bot.py` + `ingest_docs.py` |

### Running the Application

| Command | Purpose |
|---------|---------|
| `python app.py` | Development mode (port 5000) |
| `python run_server.py` | Production mode (port 80, needs admin) |
| `SETUP_AND_START.bat` | Full setup + start (Windows) |
| `START.bat` | Interactive menu (Windows) |
| `./start.sh` | Interactive menu (Linux/Mac) |

### Running Tests

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=. --cov-report=html

# Run specific test file
pytest tests/test_models.py -v
```

### Database Migrations

```bash
# Run all legacy migrations
python migrate_all.py

# Using Alembic (recommended)
alembic upgrade head           # Apply all migrations
alembic revision --autogenerate -m "description"  # Create new migration
alembic history               # View migration history
```

### Code Style

- Python: Follow PEP 8
- Use type hints where possible
- Logging: `✅` success, `❌` error, `⚠️` warning, `🔄` processing
- Comments in English, UI supports multiple languages
- All API keys must be encrypted using Fernet

### API Documentation

When running the application, API documentation is available at:
- `/docs` - Interactive Swagger UI (FastAPI)
- `/redoc` - ReDoc documentation (FastAPI)

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

## 🛠️ Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `FLASK_SECRET_KEY` | Flask session secret (required) |
| `BRAIN_CAPITAL_MASTER_KEY` | Fernet encryption key (required) |
| `DATABASE_URL` | PostgreSQL URL (optional) |
| `REDIS_URL` | Redis URL (optional) |
| `PRODUCTION_DOMAIN` | Production domain for CORS |

### Trading Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `risk_perc` | Risk percentage per trade | 3% |
| `leverage` | Leverage multiplier | 20x |
| `tp_perc` | Take Profit percentage | 5% |
| `sl_perc` | Stop Loss percentage | 2% |
| `max_positions` | Maximum open positions | 10 |

---

## 🚢 Production Deployment

### VPS Deployment (Recommended)

```bash
# One-command deploy from Windows
DEPLOY.bat

# Or from Linux/Mac
./deploy.sh
```

### Linux Server Setup

See [LINUX_DEPLOYMENT.md](LINUX_DEPLOYMENT.md) for complete guide including:
- System requirements
- Nginx configuration
- SSL certificates
- Systemd service
- PostgreSQL setup
- Auto-deploy from GitHub

### Docker (Alternative)

```bash
docker-compose up -d
```

---

## 💳 Subscription System

Built-in crypto payment support via Plisio:

| Plan | Price | Features |
|------|-------|----------|
| Basic | $29.99/mo | 3 exchanges, email support |
| Pro | $79.99/mo | 10 exchanges, priority support |
| Enterprise | $199.99/mo | Unlimited exchanges, API access |

Supported currencies: USDT (TRC20/ERC20), BTC, ETH, LTC

---

## 📱 Telegram Integration

### Notifications
- 📥 New signals received
- ✅ Trades opened
- 💰 Trades closed with PnL
- ⚠️ Errors and warnings
- 🚨 Emergency closures

### Panic Kill Switch
Close all positions with OTP verification:
```
/panic <OTP_CODE>
```

---

## 🐛 Troubleshooting

### Database Migration Error
```bash
python migrate_all.py
```

### Port 80 in Use
```bash
# Windows
fix_port.bat

# Or manually
netstat -ano | findstr :80
taskkill /PID <pid> /F
```

### Encryption Error
```bash
python setup_env.py --force
```

### Fresh Database Start
```bash
# Delete existing database
del brain_capital.db    # Windows
rm brain_capital.db     # Linux/Mac

# Restart app to create new database
python app.py
```

---

## 📈 Monitoring

Docker Compose includes:
- **Prometheus** - Metrics collection (port 9090)
- **Grafana** - Dashboards (port 3000)
- **Loki** - Log aggregation

Pre-configured dashboards for trading metrics and system health.

---

## 📄 License

MIT License - see LICENSE file

---

## 🤝 Contributing

1. Read [DEV_MANUAL.md](DEV_MANUAL.md) for architecture overview
2. Create an issue for bugs or feature requests
3. Submit pull requests with tests

---

## 📞 Support

- Check [DEV_MANUAL.md](DEV_MANUAL.md) for troubleshooting
- Check [FAQ.md](FAQ.md) for common questions
- Review application logs
- Create GitHub issues

---

**⚠️ DISCLAIMER**: Cryptocurrency trading involves significant risk. Use this software at your own risk. The developers are not responsible for any financial losses.

---

*Last Updated: January 11, 2026 (Code Audit Completed)*
