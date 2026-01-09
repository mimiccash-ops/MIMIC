# MIMIC (Brain Capital) - Frequently Asked Questions

## General Questions

### What is MIMIC?

MIMIC (Brain Capital) is an automated copy trading platform for cryptocurrency exchanges. It enables users to automatically copy trades from a master trading account across multiple exchanges (primarily Binance Futures). The platform receives trading signals via TradingView webhooks and executes them across all connected user accounts.

### How does copy trading work?

1. A master trader executes trades on their account
2. MIMIC receives trading signals via TradingView webhooks
3. The platform automatically replicates these trades on all connected user accounts
4. Users can customize their risk settings (leverage, position size, stop-loss, take-profit)

### What exchanges are supported?

MIMIC supports 30+ cryptocurrency exchanges via the CCXT library:

- **Tier 1 (Major):** Binance, Coinbase, Bybit, OKX, Upbit
- **Tier 2 (Large):** Bitget, Gate, KuCoin, Kraken, HTX
- **Tier 3 (Mid-size):** MEXC, Crypto.com, Bitstamp, Bitfinex, Bithumb
- **Tier 4+:** WhiteBit, Poloniex, Gemini, BingX, Phemex, and more

---

## Getting Started

### How do I create an account?

1. Visit the registration page at `/register`
2. Enter your username, email, and password
3. Optionally enter a referral code if you have one
4. Complete the registration form
5. Log in with your credentials

### How do I connect my exchange account?

1. Log in to your MIMIC dashboard
2. Go to "API Keys" or "Exchanges" section
3. Select your exchange from the dropdown
4. Enter your API key and API secret from your exchange
5. For some exchanges (like OKX, KuCoin), you'll also need a passphrase
6. Submit for admin approval

**Important API Key Settings for Binance:**
- ✅ Enable `Futures Trading`
- ❌ **Disable** `Enable Withdrawals` (for security)
- ✅ Enable `Restrict access to trusted IPs only` (recommended)

### What API permissions do I need?

For Binance Futures:
- Enable Futures trading permission
- Do NOT enable withdrawal permissions
- Optionally restrict to your server's IP for extra security

---

## Trading Settings

### What is risk percentage?

Risk percentage determines how much of your account balance is risked on each trade. For example, with 3% risk and a $10,000 account, each trade would risk $300.

### What is leverage?

Leverage multiplies your trading position. With 20x leverage and $100, you control a $2,000 position. Higher leverage means higher potential profits AND losses.

**Warning:** Higher leverage significantly increases risk. Start with lower leverage until you understand the platform.

### What are Take Profit (TP) and Stop Loss (SL)?

- **Take Profit (TP):** Automatically closes your position when profit reaches a certain percentage
- **Stop Loss (SL):** Automatically closes your position to limit losses at a certain percentage

For example, with 5% TP and 2% SL:
- Position closes automatically when profit reaches 5%
- Position closes automatically when loss reaches 2%

### What is DCA (Dollar Cost Averaging)?

DCA automatically adds to your position when the price moves against you. This can lower your average entry price.

Settings:
- **DCA Threshold:** When to trigger DCA (e.g., -2% means trigger when position is down 2%)
- **DCA Multiplier:** Size of DCA order relative to original (e.g., 1.0 means same size)
- **Max DCA Orders:** Maximum number of DCA orders per position

### What is Trailing Stop-Loss?

Trailing Stop-Loss dynamically adjusts your stop-loss as the price moves in your favor, locking in profits.

Settings:
- **Activation:** When to activate trailing (e.g., 1% profit)
- **Callback:** How far the price can pull back before closing (e.g., 0.5%)

---

## Subscription & Payments

### What subscription plans are available?

| Plan | Price | Features |
|------|-------|----------|
| Basic | $29.99/mo | 3 exchanges, email support |
| Pro | $79.99/mo | 10 exchanges, priority support, analytics |
| Enterprise | $199.99/mo | Unlimited exchanges, API access |

### What payment methods are accepted?

MIMIC accepts cryptocurrency payments via Plisio:
- USDT (TRC20 and ERC20)
- Bitcoin (BTC)
- Ethereum (ETH)
- Litecoin (LTC)

### How do I upgrade my subscription?

1. Go to your dashboard
2. Click "Upgrade" or "Subscription"
3. Select your desired plan
4. Complete the crypto payment
5. Your subscription activates automatically upon payment confirmation

---

## Notifications

### How do I enable Telegram notifications?

1. Start a chat with `@BrainCapitalBot` (or your platform's bot)
2. Get your Chat ID by sending `/start` to the bot
3. Enter your Telegram Chat ID in your profile settings
4. Enable Telegram notifications

### What notifications will I receive?

- 📥 New trading signals received
- ✅ Trades opened successfully
- 💰 Trades closed with profit/loss
- ⚠️ Error notifications
- 🚨 Emergency closures (panic mode)

### What is the Panic Kill Switch?

The Panic Kill Switch is an emergency feature that closes ALL positions across ALL accounts instantly. It requires 2FA (OTP) verification via Telegram for security.

To use: Send `/panic <OTP_CODE>` to the Telegram bot

---

## Risk Management

### What are Risk Guardrails?

Risk Guardrails protect your account from excessive losses in a single day:

- **Daily Drawdown Limit:** Pauses trading if daily losses exceed a threshold (e.g., 10%)
- **Daily Profit Lock:** Optionally pauses trading after reaching a profit target (e.g., 20%)

### How do I set up risk guardrails?

1. Go to your profile settings
2. Enable Risk Guardrails
3. Set your Daily Drawdown Limit (e.g., 10%)
4. Optionally set a Daily Profit Target

### What happens when guardrails trigger?

- Trading is automatically paused for your account
- You receive a notification
- Trading resumes the next day (or you can manually resume)

---

## Troubleshooting

### I'm getting "Database migration error"

Run the migration script:
```bash
python migrate_all.py
```

### My trades aren't being copied

Check the following:
1. Is your account active? (Check dashboard status)
2. Are your API keys valid and approved?
3. Is trading enabled for your exchange connection?
4. Check if you have sufficient balance on your exchange
5. Verify your leverage and margin settings on the exchange

### I can't connect my API keys

Common issues:
1. **Wrong permissions:** Ensure Futures trading is enabled
2. **IP restriction:** Add your server IP to the exchange whitelist
3. **Expired keys:** Regenerate API keys if they've expired
4. **Wrong exchange:** Make sure you're using Futures API keys, not Spot

### Port 80 is already in use

On Windows, run:
```batch
fix_port.bat
```

Or manually:
```bash
netstat -ano | findstr :80
taskkill /PID <pid> /F
```

### Encryption error

Regenerate encryption keys:
```bash
python setup_env.py --force
```

**Warning:** This will invalidate all existing encrypted data (API keys)!

---

## Security

### How are my API keys stored?

API keys are encrypted using Fernet symmetric encryption before being stored in the database. The encryption key is stored securely and never committed to version control.

### Is my data safe?

MIMIC implements multiple security measures:
- Password hashing (scrypt algorithm)
- API key encryption (Fernet)
- Rate limiting
- CSRF protection
- Session fingerprinting
- Security headers

### What should I NEVER do?

- ❌ Never enable withdrawal permissions on your exchange API keys
- ❌ Never share your API keys with anyone
- ❌ Never use weak passwords
- ❌ Never commit `.env` or `config.ini` files to Git

---

## Referral System

### How does the referral system work?

1. Get your unique referral code from your profile
2. Share it with friends
3. When they sign up and trade, you earn commission on their profitable trades
4. Commission rate is 5% of profits

### How do I get my referral code?

Go to your profile page - your referral code is displayed there. If you don't have one, click "Generate Referral Code".

### When do I receive commissions?

Commissions are credited when your referred users make profitable trades. View your commission history in your profile.

---

## Technical Questions

### What technologies does MIMIC use?

- **Backend:** Flask 3.0 + FastAPI
- **Database:** SQLite (dev) / PostgreSQL (prod)
- **Real-time:** Flask-SocketIO (WebSocket)
- **Exchange API:** CCXT (multi-exchange support)
- **Task Queue:** ARQ + Redis
- **Encryption:** Fernet (cryptography)

### Can I run MIMIC on Docker?

Yes! Use Docker Compose for production deployment:
```bash
docker-compose up -d
```

This starts all services: app, Redis, PostgreSQL, Prometheus, and Grafana.

### What ports does MIMIC use?

| Service | Port |
|---------|------|
| Web App | 80 (prod) / 5000 (dev) |
| Redis | 6379 |
| PostgreSQL | 5432 |
| Prometheus | 9090 |
| Grafana | 3000 |

---

## Contact & Support

### How do I contact support?

1. Use the AI Support Bot in the chat widget
2. Send a message via the internal messaging system
3. Contact admin through Telegram

### Where can I find more documentation?

- `README.md` - Quick start guide
- `DEV_MANUAL.md` - Complete developer documentation
- `SECURITY.md` - Security guidelines
- `SECURITY_HARDENING.md` - Production hardening guide

---

**Disclaimer:** Cryptocurrency trading involves significant risk. Use this software at your own risk. The developers are not responsible for any financial losses.

*Last Updated: January 8, 2026*
