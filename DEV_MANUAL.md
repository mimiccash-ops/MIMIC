# 🧠 MIMIC (Brain Capital) - Developer Manual

Version: 3.4  
Last Updated: January 16, 2026  
Code Audit Date: January 16, 2026

---

## 📑 Table of Contents

1. [Project Overview](#-project-overview)
2. [Architecture](#-architecture)
3. [Quick Start (Scripts)](#-quick-start-scripts)
4. [Manual Setup](#-manual-setup)
5. [Running Services](#-running-services)
6. [Docker Deployment](#-docker-deployment)
7. [Configuration](#-configuration)
8. [Frontend Assets](#-frontend-assets)
9. [Observability](#-observability)
10. [Testing](#-testing)
11. [Deployment Notes](#-deployment-notes)
12. [Code Audit & Technical Debt](#-code-audit--technical-debt)
13. [Functional Verification Checklist](#-functional-verification-checklist)
14. [Support](#-support)

---

## 🎯 Project Overview

**MIMIC (Brain Capital)** is a copy-trading platform that receives TradingView
signals via webhook and mirrors trades across connected exchange accounts.
It includes user management, risk controls, Telegram notifications, and a web
dashboard with real-time updates via Socket.IO.

---

## 🏗 Architecture

**Core components (actual codebase):**

- **Flask app**: `app.py` (routes, auth, dashboards, webhook handler, Socket.IO).
- **Trading engine**: `trading_engine.py` (trade execution, exchange adapters).
- **Background worker**: `worker.py` + `tasks.py` (ARQ + Redis).
- **Telegram bot**: `run_bot.py` (standalone polling process).
- **Notifications**: `telegram_notifier.py`, `telegram_bot.py`.
- **Security**: `security.py` (rate limiting, CSRF, session hardening).
- **Data layer**: `models.py`, migrations in `migrations/`.
- **Frontend**: Jinja templates in `templates/`, static assets in `static/`.

**Key services:**
- Database: SQLite (dev) / PostgreSQL (prod) via SQLAlchemy.
- Redis: optional for ARQ worker.
- Prometheus/Grafana/Loki: optional monitoring stack (Docker Compose).

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

**Before running the scripts:**
1. `copy config.ini.example config.ini`
2. `python setup_env.py` **or** `copy production.env.example .env`

The scripts install dependencies, build frontend CSS (Tailwind), run migrations,
then start `app.py`, `worker.py`, and optionally `run_bot.py`.

---

## 📋 Manual Setup

### 1) Python + Node dependencies
```bash
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # Linux/macOS

pip install -r requirements.txt
npm install
```

### 2) Configuration
```bash
copy config.ini.example config.ini   # Windows
cp config.ini.example config.ini     # Linux/macOS

python setup_env.py  # Generates .env with keys
```

### 3) Migrations
```bash
python migrations/migrate.py
```

### 4) Build frontend assets
```bash
npm run build     # one-time Tailwind build
# or:
npm run watch:css # dev watcher
```

---

## 🧩 Running Services

### Web app (Flask + Socket.IO)
```bash
python app.py
```

### Background worker (ARQ + Redis)
```bash
python worker.py
```
**Requires Redis** at `REDIS_URL` (default `redis://127.0.0.1:6379/0`).

### Telegram bot (optional)
```bash
python run_bot.py
```
Requires `TG_TOKEN` / `TELEGRAM_BOT_TOKEN` and `TG_CHAT_ID` in `.env` or `config.ini`.

---

## 🐳 Docker Deployment

```bash
copy docker.env.example .env   # Windows
cp docker.env.example .env     # Linux/macOS

docker compose up -d
```

Optional data migration (profile):
```bash
docker compose --profile migration up migrate
```

**Note:** Docker expects `secrets/master.key` for the master encryption key.

---

## 🛠 Configuration

### `.env` (required)
- `FLASK_SECRET_KEY` (required)
- `BRAIN_CAPITAL_MASTER_KEY` (dev only; prefer `secrets/master.key`)
- `DATABASE_URL` (optional; PostgreSQL)
- `REDIS_URL` (optional; worker queue)
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (optional)

### `config.ini`
Primary sections (from `config.ini.example`):
- `[MasterAccount]` (API keys)
- `[Webhook]` (TradingView passphrase)
- `[Settings]` (risk/leverage/limits)
- `[Telegram]` (bot token, chat id)
- `[Email]` (SMTP)
- `[PanicOTP]` (kill switch)
- `[Compliance]` (geo-blocking, TOS)
- `[SupportBot]` (OpenAI RAG)
- `[Payment]` (Plisio)

---

## 🎨 Frontend Assets

- **Templates**: `templates/*.html` (Jinja2)
- **Static**: `static/` (CSS/JS/images)
- **Tailwind**: `package.json` scripts
  - `npm run build` (minified CSS)
  - `npm run watch:css` (dev watcher)

---

## 📈 Observability

- Logs in `logs/` (created at runtime).
- Prometheus metrics defined in `metrics.py`.
- Docker stack includes Prometheus, Grafana, Loki, and Promtail.

---

## ✅ Testing

```bash
pytest tests/ -v
```

---

## 🚢 Deployment Notes

- **Windows**: `deploy.ps1`, `deploy_production.ps1`
- **Linux/macOS**: `deploy.sh`
- **Systemd units**: `mimic.service`, `mimic-worker.service`, `mimic-bot.service`

---

## 📋 Code Audit & Technical Debt

### Audit Summary (January 16, 2026)
**Scope:** Python modules, templates, static assets, scripts, and docs.  
**Method:** Static review + dependency scan + TODO/FIXME search.

### TODO / FIXME / HACK Scan
**Results:** 0 TODO-style comments found in code.

### Technical Debt List
1. **Monolithic `app.py`**: Large file with many concerns; harder to test/maintain.
2. **Large `trading_engine.py`**: Complex async logic would benefit from more unit tests.
3. **No frontend test suite**: UI regressions rely on manual testing only.
4. **Log growth risk**: File handlers write to `logs/*.log` without rotation.
5. **Unused FastAPI deps**: `fastapi`/`uvicorn` in `requirements.txt` but no FastAPI app present.

---

## 🔎 Functional Verification Checklist

Use this after changes to validate backend + frontend behavior:

1. **Startup**: `start_server.bat` / `start_server.sh` succeeds with migrations.
2. **Web UI**: `/login`, `/register`, `/dashboard` render without errors.
3. **Webhook**: POST to `/webhook` with a valid payload returns success.
4. **Socket.IO**: Dashboard receives live updates after login.
5. **Worker**: `worker.py` connects to Redis and processes tasks.
6. **Telegram Bot**: `run_bot.py` polls successfully with valid credentials.
7. **Tailwind**: `npm run build` generates updated CSS in `static/css`.

---

## 📞 Support

1. Review logs in `logs/`
2. Check `README.md` and `FAQ.md`
3. Review `LINUX_DEPLOYMENT.md` for production details

---

**⚠️ DISCLAIMER**: Cryptocurrency trading involves significant risk. Use this software at your own risk.
