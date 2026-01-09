# MIMIC Public Developer API

The MIMIC Public API allows you to programmatically interact with the MIMIC copy trading platform. You can send trading signals and execute orders on your connected exchanges.

**Base URL:** `https://api.mimic.cash/v1`

## Authentication

All API requests require HMAC-SHA256 signature authentication. Include these headers with every request:

| Header | Description |
|--------|-------------|
| `X-API-Key` | Your API key (starts with `mk_`) |
| `X-Timestamp` | Current Unix timestamp (seconds) |
| `X-Signature` | HMAC-SHA256 signature |

### Generating the Signature

```python
import hmac
import hashlib
import time
import json

def create_signature(api_secret, timestamp, method, path, body=""):
    """
    Create HMAC-SHA256 signature for API authentication.
    
    Args:
        api_secret: Your API secret (starts with 'ms_')
        timestamp: Unix timestamp (string)
        method: HTTP method (GET, POST, etc.)
        path: Request path (e.g., '/v1/signal')
        body: Request body (JSON string for POST requests)
    
    Returns:
        Hex-encoded signature
    """
    message = f"{timestamp}{method.upper()}{path}{body}"
    signature = hmac.new(
        api_secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature

# Example usage
api_key = "mk_your_api_key_here"
api_secret = "ms_your_api_secret_here"
timestamp = str(int(time.time()))
method = "POST"
path = "/v1/signal"
body = json.dumps({"symbol": "BTCUSDT", "action": "open_long"})

signature = create_signature(api_secret, timestamp, method, path, body)

headers = {
    "X-API-Key": api_key,
    "X-Timestamp": timestamp,
    "X-Signature": signature,
    "Content-Type": "application/json"
}
```

### JavaScript Example

```javascript
const crypto = require('crypto');

function createSignature(apiSecret, timestamp, method, path, body = '') {
    const message = `${timestamp}${method.toUpperCase()}${path}${body}`;
    return crypto
        .createHmac('sha256', apiSecret)
        .update(message)
        .digest('hex');
}

// Example usage
const apiKey = 'mk_your_api_key_here';
const apiSecret = 'ms_your_api_secret_here';
const timestamp = Math.floor(Date.now() / 1000).toString();
const method = 'POST';
const path = '/v1/signal';
const body = JSON.stringify({ symbol: 'BTCUSDT', action: 'open_long' });

const signature = createSignature(apiSecret, timestamp, method, path, body);

const headers = {
    'X-API-Key': apiKey,
    'X-Timestamp': timestamp,
    'X-Signature': signature,
    'Content-Type': 'application/json'
};
```

## Rate Limiting

- Default: **60 requests per minute** per API key
- Rate limit can be configured per key (10-120 req/min)
- Headers returned:
  - `X-RateLimit-Limit`: Your rate limit
  - `X-RateLimit-Remaining`: Remaining requests
  - `X-RateLimit-Reset`: Unix timestamp when limit resets

## Endpoints

### POST /v1/signal

Submit a trading signal to be executed on your connected exchanges.

**Required Permission:** `signal`

**Request Body:**

```json
{
    "symbol": "BTCUSDT",
    "action": "open_long",
    "leverage": 10,
    "risk_percent": 2.0,
    "stop_loss": 41000,
    "take_profit": 45000,
    "comment": "My trading bot signal"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `symbol` | string | Yes | Trading pair (e.g., `BTCUSDT`) |
| `action` | string | Yes | Signal action: `open_long`, `open_short`, `close_long`, `close_short`, `close_all` |
| `leverage` | integer | No | Leverage (1-125) |
| `risk_percent` | float | No | Risk percentage of balance (0.1-100) |
| `quantity` | float | No | Position size (overrides risk_percent) |
| `stop_loss` | float | No | Stop loss price |
| `take_profit` | float | No | Take profit price |
| `comment` | string | No | Optional tag/comment (max 200 chars) |

**Response:**

```json
{
    "success": true,
    "signal_id": "sig_1704067200_123",
    "message": "Signal queued for processing",
    "processed_users": 1,
    "timestamp": "2024-01-01T00:00:00.000Z"
}
```

---

### POST /v1/orders

Execute a trade order directly on your connected exchanges.

**Required Permission:** `trade`

**Request Body:**

```json
{
    "symbol": "BTCUSDT",
    "side": "long",
    "type": "market",
    "quantity": 0.01,
    "leverage": 10,
    "stop_loss": 41000,
    "take_profit": 45000
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `symbol` | string | Yes | Trading pair |
| `side` | string | Yes | Order side: `buy`, `sell`, `long`, `short` |
| `type` | string | No | Order type: `market` (default), `limit` |
| `quantity` | float | No | Order quantity |
| `price` | float | No | Limit price (required for limit orders) |
| `leverage` | integer | No | Leverage |
| `reduce_only` | boolean | No | Reduce-only order (default: false) |
| `stop_loss` | float | No | Stop loss price |
| `take_profit` | float | No | Take profit price |

**Response:**

```json
{
    "success": true,
    "order_id": "ord_1704067200_123",
    "message": "Order submitted for execution",
    "symbol": "BTCUSDT",
    "side": "long",
    "quantity": 0.01,
    "price": 43500.00,
    "timestamp": "2024-01-01T00:00:00.000Z"
}
```

---

### GET /v1/account

Get your account information including balance and subscription status.

**Required Permission:** `read`

**Response:**

```json
{
    "user_id": 123,
    "username": "trader1",
    "balance": 10000.00,
    "available_balance": 8500.00,
    "total_pnl": 1500.00,
    "open_positions": 3,
    "subscription_active": true,
    "subscription_plan": "pro"
}
```

---

### GET /v1/positions

Get your current open positions across all connected exchanges.

**Required Permission:** `read`

**Response:**

```json
[
    {
        "symbol": "BTCUSDT",
        "side": "long",
        "quantity": 0.1,
        "entry_price": 42000.00,
        "mark_price": 43500.00,
        "unrealized_pnl": 150.00,
        "leverage": 10,
        "liquidation_price": 38000.00
    }
]
```

---

## Error Responses

All errors follow this format:

```json
{
    "success": false,
    "error": "Error message",
    "code": "ERROR_CODE",
    "timestamp": "2024-01-01T00:00:00.000Z"
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `401` | 401 | Invalid API key or signature |
| `403` | 403 | Insufficient permissions or no active subscription |
| `429` | 429 | Rate limit exceeded |
| `400` | 400 | Invalid request body |
| `500` | 500 | Internal server error |

---

## API Key Permissions

When creating an API key, you can configure permissions:

| Permission | Description |
|------------|-------------|
| `read` | View account info and positions |
| `signal` | Submit trading signals |
| `trade` | Execute direct orders |

---

## IP Whitelisting

For additional security, you can restrict your API key to specific IP addresses when creating it.

---

## Full Python Example

```python
import requests
import hmac
import hashlib
import json
import time

class MimicAPI:
    BASE_URL = "https://api.mimic.cash/v1"
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
    
    def _sign(self, method: str, path: str, body: str = "") -> dict:
        timestamp = str(int(time.time()))
        message = f"{timestamp}{method.upper()}{path}{body}"
        signature = hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return {
            "X-API-Key": self.api_key,
            "X-Timestamp": timestamp,
            "X-Signature": signature,
            "Content-Type": "application/json"
        }
    
    def send_signal(self, symbol: str, action: str, **kwargs):
        """Send a trading signal."""
        path = "/v1/signal"
        body = json.dumps({
            "symbol": symbol,
            "action": action,
            **kwargs
        })
        headers = self._sign("POST", path, body)
        response = requests.post(f"{self.BASE_URL}{path}", headers=headers, data=body)
        return response.json()
    
    def execute_order(self, symbol: str, side: str, **kwargs):
        """Execute a trade order."""
        path = "/v1/orders"
        body = json.dumps({
            "symbol": symbol,
            "side": side,
            **kwargs
        })
        headers = self._sign("POST", path, body)
        response = requests.post(f"{self.BASE_URL}{path}", headers=headers, data=body)
        return response.json()
    
    def get_account(self):
        """Get account information."""
        path = "/v1/account"
        headers = self._sign("GET", path)
        response = requests.get(f"{self.BASE_URL}{path}", headers=headers)
        return response.json()
    
    def get_positions(self):
        """Get open positions."""
        path = "/v1/positions"
        headers = self._sign("GET", path)
        response = requests.get(f"{self.BASE_URL}{path}", headers=headers)
        return response.json()


# Usage example
if __name__ == "__main__":
    api = MimicAPI(
        api_key="mk_your_api_key_here",
        api_secret="ms_your_api_secret_here"
    )
    
    # Get account info
    print(api.get_account())
    
    # Send a signal to open a long position
    result = api.send_signal(
        symbol="BTCUSDT",
        action="open_long",
        leverage=10,
        risk_percent=2.0,
        stop_loss=41000,
        take_profit=45000
    )
    print(result)
```

---

## Running the API Server

### Standalone (Development)

```bash
# Run the public API on port 8001
python public_api.py
```

### With Main App (Production)

The public API is automatically mounted when running the main FastAPI app. It's accessible at:
- `/api/public/v1/signal`
- `/api/public/v1/orders`
- etc.

Or configure `api.mimic.cash` subdomain to point to the standalone server.

### Environment Variables

```bash
# Required for production
FLASK_ENV=production
DATABASE_URL=postgresql://user:pass@host:5432/db
REDIS_URL=redis://localhost:6379/0
```

---

## Support

For API support, contact: support@mimic.cash

Interactive documentation: [https://api.mimic.cash/docs](https://api.mimic.cash/docs)
