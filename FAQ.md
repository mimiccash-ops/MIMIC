# Frequently Asked Questions

## Getting Started

### What is MIMIC?

MIMIC is an automated copy trading platform for cryptocurrency. When our master trader makes a trade, the same trade is automatically copied to your connected exchange account. You set your risk level, and we handle the rest.

### How does copy trading work?

1. Connect your exchange account using API keys
2. Configure your risk settings (how much to risk per trade)
3. Our system automatically copies trades to your account
4. You can monitor everything from your dashboard

### What exchanges are supported?

We support 30+ major exchanges including:
- **Binance** (most popular)
- **Bybit**
- **OKX**
- **KuCoin**
- **Bitget**
- **Gate.io**
- And many more

---

## Account Setup

### How do I connect my exchange?

1. Log in to your exchange (e.g., Binance)
2. Create a new API key with **Futures trading** enabled
3. **Important:** Do NOT enable withdrawals for security
4. Copy your API Key and Secret
5. Paste them in your MIMIC dashboard under "Exchanges"
6. Wait for admin approval (usually within 24 hours)

### What permissions should my API key have?

| Permission | Required? |
|------------|-----------|
| Futures Trading | ✅ Yes |
| Spot Trading | ❌ No |
| Withdrawals | ❌ **Never enable this** |
| IP Restriction | ✅ Recommended |

---

## Trading Settings

### What is Risk Percentage?

This is how much of your account you're willing to risk on each trade. 

**Example:** With 3% risk and a $10,000 account, each trade risks about $300.

**Recommendation:** Start with 1-3% if you're new to trading.

### What is Leverage?

Leverage multiplies your position size. With 20x leverage and $100, you control a $2,000 position.

⚠️ **Warning:** Higher leverage = higher risk. Start with lower leverage (5-10x) until you're comfortable.

### What are Take Profit and Stop Loss?

- **Take Profit (TP):** Automatically closes your trade when you reach a target profit
- **Stop Loss (SL):** Automatically closes your trade to limit losses

**Example:** With 5% TP and 2% SL:
- Your trade closes when profit hits 5%
- Your trade closes if loss reaches 2%

### What is DCA (Dollar Cost Averaging)?

DCA adds to your position when the price moves against you, lowering your average entry price.

- **DCA Threshold:** How far the price must drop before adding (e.g., -2%)
- **DCA Multiplier:** How much to add relative to original position
- **Max DCA Orders:** Maximum times to add to a position

### What is Trailing Stop-Loss?

A smart stop-loss that follows the price as it moves in your favor, locking in profits while giving room for the trade to run.

---

## Subscription & Payments

### What plans are available?

| Plan | Price | Exchanges |
|------|-------|-----------|
| Basic | $29.99/month | Up to 3 |
| Pro | $79.99/month | Up to 10 |
| Enterprise | $199.99/month | Unlimited |

### How do I pay?

We accept cryptocurrency payments:
- USDT (TRC20 or ERC20)
- Bitcoin (BTC)
- Ethereum (ETH)
- Litecoin (LTC)

Your subscription activates automatically after payment confirmation.

---

## Notifications

### How do I set up Telegram notifications?

1. Open Telegram and search for `@BrainCapitalBot`
2. Send `/start` to get your Chat ID
3. Enter this Chat ID in your MIMIC profile settings
4. Enable Telegram notifications

### What notifications will I receive?

- ✅ Trade opened
- 💰 Trade closed (with profit/loss)
- ⚠️ Errors or issues
- 🚨 Emergency alerts

---

## Risk Management

### What are Risk Guardrails?

Safety features that automatically pause trading when:
- **Daily losses** exceed your limit (e.g., stop after losing 10%)
- **Daily profits** hit your target (optional)

This prevents emotional overtrading and protects your account.

### What is the Panic Kill Switch?

An emergency button that closes ALL your positions instantly. Use it if you need to exit everything quickly. Requires verification via Telegram for security.

---

## Troubleshooting

### My trades aren't being copied

Check these common issues:
1. Is your account status "Active" in the dashboard?
2. Are your API keys approved?
3. Do you have enough balance on your exchange?
4. Is trading enabled for your connected exchange?

### I can't connect my API keys

Common causes:
1. **Missing permissions:** Make sure Futures trading is enabled
2. **Wrong key type:** Use Futures API keys, not Spot
3. **IP restrictions:** Add your server's IP to the exchange whitelist
4. **Expired keys:** Generate new API keys and try again

---

## Security

### Are my API keys safe?

Yes. Your API keys are encrypted before storage and never stored in plain text.

### Security Best Practices

- ✅ **Never** enable withdrawal permissions on your API keys
- ✅ Use a strong, unique password
- ✅ Enable IP restrictions on your exchange API keys
- ✅ Set up Telegram notifications to monitor activity

---

## Referrals

### How do referrals work?

1. Get your referral code from your profile
2. Share it with friends
3. Earn 5% commission on their profitable trades

---

## Need Help?

- **AI Support Bot:** Click the chat icon in the bottom right corner
- **Messages:** Send a message through your dashboard
- **Telegram:** Contact our support bot

---

**Disclaimer:** Cryptocurrency trading involves significant risk. Past performance does not guarantee future results. Only trade with money you can afford to lose.

*Last Updated: January 2026*
