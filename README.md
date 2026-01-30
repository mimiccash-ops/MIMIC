# 🧠 MIMIC (Brain Capital)

**Automated Copy Trading Platform for Cryptocurrency Exchanges**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-3.0-green.svg)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

MIMIC receives TradingView webhook signals and mirrors trades across connected user accounts. It supports 30+ exchanges via CCXT, includes risk controls, real-time dashboards, Telegram notifications, and optional monitoring via Docker Compose.

---

## ✨ Key Features

- 🔄 **Automatic Copy Trading** - Mirror master account trades to users
- 📊 **TradingView Webhooks** - Alert-driven trade execution
- 🔐 **Encrypted API Keys** - Fernet-based encryption for all credentials
- 📱 **Telegram Notifications** - Real-time alerts and bot commands
- 📈 **Real-time Dashboard** - Socket.IO live updates
- 🛡️ **Risk Controls** - TP/SL, leverage limits, position caps
- 🧠 **Smart Features** - Trailing SL, DCA, risk guardrails
- 🏆 **Gamification** - XP, levels, achievements, tournaments
- 💳 **Crypto Payments** - Plisio integration for subscriptions
- 🌍 **Multi-Exchange** - 30+ exchanges via CCXT
- 🐳 **Docker Ready** - Full Docker Compose stack with monitoring

---

## 🚀 Quick Start

### Windows

```batch
start_server.bat
```

### Linux / macOS

```bash
chmod +x start_server.sh
./start_server.sh
```

### Before Running

1. Copy configuration files:
   ```bash
   copy config.ini.example config.ini    # Windows
   cp config.ini.example config.ini      # Linux/macOS
   ```

2. Generate environment file:
   ```bash
   python setup_env.py
   # OR manually: copy production.env.example .env
   ```

3. Edit `config.ini` with your API credentials

The scripts will:
- Install dependencies (Python + Node.js)
- Build frontend CSS (Tailwind)
- Run database migrations
- Start web app + worker + Telegram bot

---

## 🛠 Manual Installation

### Prerequisites

- **Python 3.10+**
- **Node.js + npm** (for Tailwind CSS build)
- **Redis** (required for background worker)
- **PostgreSQL** (recommended for production)

### Step-by-Step Setup

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate    # Linux/macOS
venv\Scripts\activate       # Windows

# 2. Install dependencies
pip install -r requirements.txt
npm install

# 3. Configure application
cp config.ini.example config.ini
python setup_env.py         # Generates .env with secure keys

# 4. Run database migrations
python migrations/migrate.py

# 5. Build frontend
npm run build
```

### Running Services

```bash
# Web application (Flask + Socket.IO)
python app.py

# Background worker (requires Redis)
python worker.py

# Telegram bot (optional)
python run_bot.py
```

---

## 🐳 Docker Deployment

```bash
# Copy environment file
cp docker.env.example .env

# Create encryption key
mkdir -p secrets
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" > secrets/master.key

# Start all services
docker compose up -d
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| `web` | 5000 | Flask web application |
| `worker` | 9091 | Background task worker |
| `db` | 5432 | PostgreSQL database |
| `redis` | 6379 | Task queue |
| `grafana` | 3000 | Monitoring dashboards |
| `prometheus` | 9090 | Metrics collection |

### Data Migration

```bash
docker compose --profile migration up migrate
```

---

## 📁 Project Structure

```
MIMIC/
├── app.py                # Main Flask application
├── trading_engine.py     # Copy trading engine
├── worker.py             # ARQ background worker
├── tasks.py              # Task definitions
├── run_bot.py            # Telegram bot runner
├── config.py             # Configuration loader
├── models.py             # SQLAlchemy models
├── security.py           # Security utilities
├── templates/            # Jinja2 HTML templates
├── static/               # CSS/JS/images
├── migrations/           # Database migrations
├── tests/                # Test suite
├── monitoring/           # Prometheus/Grafana configs
├── docker-compose.yml    # Docker orchestration
├── requirements.txt      # Python dependencies
└── package.json          # Frontend build scripts
```

---

## ⚙️ Configuration

### Required Files

| File | Source | Description |
|------|--------|-------------|
| `config.ini` | `config.ini.example` | API keys, trading settings |
| `.env` | `production.env.example` or `setup_env.py` | Environment variables |
| `secrets/master.key` | Generate with script | Encryption key |

### Key Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `FLASK_SECRET_KEY` | ✅ | Session encryption (32+ chars) |
| `DATABASE_URL` | ❌ | PostgreSQL URL |
| `REDIS_URL` | ❌ | Redis URL for worker |
| `TELEGRAM_BOT_TOKEN` | ❌ | Telegram notifications |

### Master Key Setup

For production, use one of these methods (in order of preference):

1. **Docker Secret:** `./secrets/master.key`
2. **Secure file:** `/etc/brain_capital/master.key`
3. **Environment variable:** `BRAIN_CAPITAL_MASTER_KEY`

Generate a key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## 🧑‍💻 Development

### Running Tests

```bash
pytest tests/ -v

# With coverage
pytest tests/ --cov=. --cov-report=html
```

### Frontend Development

```bash
# Watch mode (auto-rebuild on changes)
npm run watch:css

# Production build
npm run build
```

### Code Quality

```bash
# Linting
flake8 *.py

# Formatting
black *.py

# Security scan
bandit -r . -x ./venv
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [DEV_MANUAL.md](DEV_MANUAL.md) | Comprehensive developer guide |
| [FAQ.md](FAQ.md) | Frequently asked questions |
| [SECURITY.md](SECURITY.md) | Security practices |
| [LINUX_DEPLOYMENT.md](LINUX_DEPLOYMENT.md) | Linux deployment guide |
| [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) | Production checklist |

---

## 🔐 Security

- All API keys are encrypted with Fernet (AES-128)
- Passwords hashed with bcrypt
- CSRF protection on all forms
- Rate limiting on sensitive endpoints
- Session security (HTTP-only, SameSite cookies)
- WebAuthn/Passkeys support
- 2FA for panic kill switch

See [SECURITY.md](SECURITY.md) for details.

---

## 📊 Monitoring

The Docker stack includes:
- **Prometheus** - Metrics collection
- **Grafana** - Dashboards and alerting
- **Loki** - Log aggregation
- **Promtail** - Log shipping

Access Grafana at `http://localhost:3000` (default: admin/braincapital2024)

---

## 📄 License

MIT License - see `LICENSE`

---

## 📞 Support

1. **Live Chat:** Click the chat icon in the dashboard
2. **Documentation:** Read [DEV_MANUAL.md](DEV_MANUAL.md)
3. **FAQ:** Check [FAQ.md](FAQ.md)
4. **Logs:** Review `logs/` directory

---

**⚠️ DISCLAIMER:** Cryptocurrency trading involves significant risk. Past performance does not guarantee future results. Use this software at your own risk.

---

*Last Updated: January 18, 2026*
