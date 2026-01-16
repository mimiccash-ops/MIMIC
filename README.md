# 🧠 MIMIC (Brain Capital)

**Automated Copy Trading Platform for Cryptocurrency Exchanges**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-3.0-green.svg)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

MIMIC receives TradingView webhook signals and mirrors trades across connected
user accounts. It includes risk controls, real-time dashboards, Telegram
notifications, and optional monitoring via Docker Compose.

---

## ✨ Key Features

- 🔄 **Automatic Copy Trading** - Mirror master account trades
- 📊 **TradingView Webhooks** - Alert-driven execution
- 🔐 **Encrypted API Keys** - Fernet-based key storage
- 📱 **Telegram Notifications** - Real-time alerts and bot commands
- 📈 **Real-time Dashboard** - Socket.IO live updates
- 🛡️ **Risk Controls** - TP/SL, leverage, position caps
- 🧠 **Smart Features** - Trailing SL, DCA, risk guardrails

---

## 🚀 Quick Start (Recommended)

### Windows
```batch
start_server.bat
```

### Linux / macOS
```bash
chmod +x start_server.sh
./start_server.sh
```

**Before running the scripts:**
1. `copy config.ini.example config.ini`
2. `python setup_env.py` **or** `copy production.env.example .env`

The scripts install dependencies, build frontend CSS, run migrations, and
start the web app + worker (+ Telegram bot if configured).

---

## 🛠 Manual Installation

### Prerequisites
- **Python 3.10+**
- **Node.js + npm** (Tailwind CSS build)
- **Redis** (required for `worker.py`)
- **PostgreSQL** (optional for production)

### Setup
```bash
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # Linux/macOS

pip install -r requirements.txt
npm install

copy config.ini.example config.ini   # Windows
cp config.ini.example config.ini     # Linux/macOS

python setup_env.py
python migrations/migrate.py
```

### Run services
```bash
python app.py       # Web app
python worker.py    # Background tasks (Redis required)
python run_bot.py   # Telegram bot (optional)
```

---

## 🐳 Docker Deployment

```bash
copy docker.env.example .env   # Windows
cp docker.env.example .env     # Linux/macOS

docker compose up -d
```

Optional data migration profile:
```bash
docker compose --profile migration up migrate
```

---

## 📁 Project Structure (Actual)

```
MIMIC/
├── app.py                # Main Flask app + Socket.IO
├── trading_engine.py     # Copy trading engine
├── worker.py             # ARQ worker (Redis)
├── tasks.py              # Background task definitions
├── run_bot.py            # Telegram bot runner
├── config.py             # Configuration loader
├── models.py             # SQLAlchemy models
├── security.py           # Security utilities
├── templates/            # Jinja2 HTML
├── static/               # CSS/JS/images
├── migrations/           # DB migrations
├── start_server.bat      # Windows start script
├── start_server.sh       # Linux/macOS start script
├── docker-compose.yml    # Docker stack
├── requirements.txt      # Python deps
└── package.json          # Tailwind build scripts
```

📚 Full developer guide: [DEV_MANUAL.md](DEV_MANUAL.md)

---

## 🧑‍💻 Developer Notes

### Key Files
- `app.py` - Flask routes, auth, Socket.IO
- `trading_engine.py` - Trade execution logic
- `models.py` - Database schema
- `templates/` + `static/` - Frontend UI
- `worker.py` - Background tasks

### Running Tests
```bash
pytest tests/ -v
```

---

## 🔐 Configuration Notes

**Required:**
- `config.ini` (from `config.ini.example`)
- `.env` (from `setup_env.py` or `production.env.example`)

**Master Key:**
`config.py` prefers `secrets/master.key` or Docker secrets for production.

---

## 📄 License

MIT License - see `LICENSE`

---

## 📞 Support

- Read `DEV_MANUAL.md`
- Check `FAQ.md`
- Review logs in `logs/`

---

*Last Updated: January 16, 2026*
