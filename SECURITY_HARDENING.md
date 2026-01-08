# Brain Capital - Security Hardening Guide

This document describes the security measures implemented in Brain Capital and provides instructions for secure deployment.

## Table of Contents

1. [Master Encryption Key Security](#master-encryption-key-security)
2. [Telegram Kill Switch (Panic Button)](#telegram-kill-switch-panic-button)
3. [Configuration Security](#configuration-security)
4. [Docker Secrets Setup](#docker-secrets-setup)
5. [Quick Setup Checklist](#quick-setup-checklist)

---

## Master Encryption Key Security

### Overview

The `BRAIN_CAPITAL_MASTER_KEY` is a Fernet encryption key used to encrypt sensitive data like API secrets stored in the database. **This key must be protected at all costs** - if compromised, attackers can decrypt all stored API credentials.

### Secure Key Loading Priority

The application loads the master key from these sources in order of priority:

1. **Docker Secret** (RECOMMENDED for production)
   - Path: `/run/secrets/brain_capital_master_key`
   - Most secure option for containerized deployments

2. **Secure System File** (for non-Docker deployments)
   - Path: `/etc/brain_capital/master.key`
   - Must be outside the web root with restricted permissions

3. **Alternative Docker Secret**
   - Path: `/run/secrets/master_key`
   - Fallback for different secret naming conventions

4. **Local Development File**
   - Path: `./secrets/master.key`
   - For development only, NOT for production

5. **Environment Variable** (NOT RECOMMENDED)
   - Variable: `BRAIN_CAPITAL_MASTER_KEY`
   - Legacy fallback - logs a security warning in production

### Generating a Master Key

```bash
# Generate a new Fernet key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Save to secrets file (for Docker/development)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" > secrets/master.key

# Or save to secure system path (for production without Docker)
sudo mkdir -p /etc/brain_capital
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" | sudo tee /etc/brain_capital/master.key
sudo chmod 600 /etc/brain_capital/master.key
sudo chown root:root /etc/brain_capital/master.key
```

---

## Telegram Kill Switch (Panic Button)

### Overview

The Telegram bot includes an emergency "Kill Switch" that allows authorized users to close ALL positions across ALL accounts (master + slaves) instantly. This is protected by **2FA (TOTP)** to prevent unauthorized use.

### Command

```
/panic_close_all <OTP_CODE>
```

Example: `/panic_close_all 123456`

### Security Features

1. **User Authorization** - Only Telegram user IDs in the `PANIC_AUTHORIZED_USERS` list can use panic commands
2. **OTP Verification** - Requires a valid 6-digit TOTP code from an authenticator app
3. **Rate Limiting** - Maximum 3 panic attempts per 5 minutes
4. **OTP Failure Lockout** - 5 wrong OTP codes = 15-minute lockout
5. **Audit Logging** - All panic attempts are logged with user details
6. **Admin Notifications** - Unauthorized attempts notify the admin chat

### Setup Instructions

#### Step 1: Generate OTP Secret

```bash
python -c "import pyotp; print(pyotp.random_base32())"
```

Save this secret (e.g., `JBSWY3DPEHPK3PXP`)

#### Step 2: Add to Authenticator App

1. Open Google Authenticator, Authy, or another TOTP app
2. Add new account manually:
   - **Account name**: `MIMIC/BrainCapital` (or any name you prefer)
   - **Secret key**: The key generated in Step 1
   - **Type**: Time-based (TOTP)
3. Verify the code changes every 30 seconds

#### Step 3: Configure Environment Variables

```bash
# Add to your .env file
PANIC_OTP_SECRET=JBSWY3DPEHPK3PXP
PANIC_AUTHORIZED_USERS=123456789,987654321
```

Get your Telegram user ID from [@userinfobot](https://t.me/userinfobot)

#### Step 4: Test the Kill Switch

1. Start a chat with your bot
2. Send `/start` to verify you're authorized
3. Send `/status` to check OTP is configured
4. **DO NOT test `/panic_close_all` with real positions!** Use testnet first.

### Alternative: Using config.ini

If you prefer config.ini over environment variables:

```ini
[PanicOTP]
secret = JBSWY3DPEHPK3PXP
authorized_users = 123456789,987654321
```

---

## Configuration Security

### Sensitive Values Removed from config.ini

The following values should **NEVER** be hardcoded in config.ini:

- API keys and secrets
- Webhook passphrases
- Telegram bot tokens
- SMTP passwords
- Encryption keys

Instead, use environment variables or Docker Secrets.

### config.ini Placeholders

The default config.ini now uses `${VARIABLE_NAME}` placeholders:

```ini
[MasterAccount]
api_key = ${BINANCE_MASTER_API_KEY}
api_secret = ${BINANCE_MASTER_API_SECRET}

[Webhook]
passphrase = ${WEBHOOK_PASSPHRASE}

[Telegram]
bot_token = ${TELEGRAM_BOT_TOKEN}
chat_id = ${TELEGRAM_CHAT_ID}
```

The application will:
1. First check for the environment variable
2. If not found, use the config.ini value (if it's not a placeholder)

---

## Docker Secrets Setup

### For Docker Compose (Development/Single Server)

1. Create the secrets directory:
   ```bash
   mkdir -p secrets
   ```

2. Create the master key file:
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" > secrets/master.key
   ```

3. The docker-compose.yml references this file:
   ```yaml
   secrets:
     brain_capital_master_key:
       file: ./secrets/master.key
   ```

### For Docker Swarm (Production Cluster)

1. Initialize swarm mode:
   ```bash
   docker swarm init
   ```

2. Create the secret from a file:
   ```bash
   docker secret create brain_capital_master_key secrets/master.key
   rm secrets/master.key  # Delete the file after creating secret
   ```

3. Or create from stdin (more secure):
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" | \
     docker secret create brain_capital_master_key -
   ```

4. Use external secrets in docker-compose.yml:
   ```yaml
   secrets:
     brain_capital_master_key:
       external: true
   ```

---

## Quick Setup Checklist

### Development Environment

- [ ] Copy `production.env.example` to `.env`
- [ ] Generate `FLASK_SECRET_KEY`: `python -c "import secrets; print(secrets.token_hex(32))"`
- [ ] Create `secrets/master.key` with Fernet key
- [ ] Set Binance API credentials in `.env`
- [ ] Set Telegram bot token in `.env`
- [ ] (Optional) Set up panic OTP for kill switch

### Production Environment

- [ ] Use Docker Secrets for master key (not env var)
- [ ] Generate strong, unique values for all secrets
- [ ] Enable HTTPS (`HTTPS_ENABLED=true`)
- [ ] Use PostgreSQL instead of SQLite
- [ ] Set proper `PRODUCTION_DOMAIN`
- [ ] Configure panic kill switch with OTP
- [ ] Set up reverse proxy (nginx) with SSL
- [ ] Enable firewall, allow only ports 80/443
- [ ] Set file permissions: `chmod 600` for all secret files
- [ ] Verify security validation passes on startup

### Environment Variables Summary

| Variable | Required | Description |
|----------|----------|-------------|
| `FLASK_SECRET_KEY` | ✅ Yes | Session encryption key (32+ chars) |
| `FLASK_ENV` | ✅ Yes | Set to `production` |
| `DATABASE_URL` | ✅ Yes | PostgreSQL connection string |
| `BINANCE_MASTER_API_KEY` | ✅ Yes | Binance API key |
| `BINANCE_MASTER_API_SECRET` | ✅ Yes | Binance API secret |
| `WEBHOOK_PASSPHRASE` | ✅ Yes | TradingView webhook secret |
| `TELEGRAM_BOT_TOKEN` | Recommended | Telegram bot for notifications |
| `TELEGRAM_CHAT_ID` | Recommended | Admin chat ID |
| `PANIC_OTP_SECRET` | Recommended | TOTP secret for kill switch |
| `PANIC_AUTHORIZED_USERS` | Recommended | Authorized Telegram user IDs |
| `REDIS_URL` | Recommended | Redis for task queue |
| `PRODUCTION_DOMAIN` | Recommended | Your domain with https:// |
| `HTTPS_ENABLED` | Recommended | Set to `true` when SSL active |

---

## Security Incident Response

### If Master Key is Compromised

1. **Immediately** generate a new master key
2. **Re-encrypt** all API credentials in the database:
   ```bash
   # This will require manual intervention - contact support
   ```
3. **Rotate** all API keys on Binance
4. **Review** access logs for unauthorized activity
5. **Update** the key using Docker Secrets

### If Panic Command is Misused

1. **Review** Telegram bot logs for unauthorized attempts
2. **Regenerate** the OTP secret
3. **Update** authorized user list
4. **Consider** additional verification steps

---

## Additional Resources

- [Docker Secrets Documentation](https://docs.docker.com/engine/swarm/secrets/)
- [TOTP/HOTP Standard (RFC 6238)](https://datatracker.ietf.org/doc/html/rfc6238)
- [Fernet Encryption Spec](https://github.com/fernet/spec)
- [OWASP Security Guidelines](https://owasp.org/www-project-web-security-testing-guide/)
