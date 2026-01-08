# Exchange Management System

Complete implementation of the Exchange Management System for the Crypto Copy-Trading Bot.

## Overview

This system provides secure, multi-exchange support with an approval workflow. Users can add exchange API keys, but they cannot be used for trading until an Admin explicitly approves them.

## Architecture

### Components

1. **Database Model** (`models.py`)
   - `UserExchange` table with all required fields
   - Encryption/decryption methods for API secrets

2. **Pydantic Schemas** (`schemas.py`)
   - Request/response validation
   - Type-safe data structures

3. **Security Service** (`security.py`)
   - `encrypt_secret()` - Encrypts sensitive data using Fernet
   - `decrypt_secret()` - Decrypts encrypted data

4. **Exchange Validator** (`service_validator.py`)
   - `validate_and_connect()` - Dynamic CCXT validation
   - Supports multiple exchanges (Binance, Bybit, OKX, Gate, MEXC, etc.)

5. **FastAPI Routers** (`routers.py`)
   - User endpoints: `/user/exchanges`
   - Admin endpoints: `/admin/exchanges`

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure environment variables are set:
```bash
export BRAIN_CAPITAL_MASTER_KEY="your-fernet-key-here"
```

3. Run database migrations (if needed):
```python
from app import app
from models import db
with app.app_context():
    db.create_all()
```

## Running the FastAPI Server

### Option 1: Direct execution
```bash
python app_fastapi.py
```

### Option 2: Using uvicorn
```bash
uvicorn app_fastapi:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at:
- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### User Endpoints (`/user/exchanges`)

#### POST `/user/exchanges/`
Add a new exchange connection.

**Request:**
```json
{
  "exchange_name": "binance",
  "api_key": "your_api_key",
  "api_secret": "your_api_secret",
  "passphrase": null,
  "label": "My Scalping Account"
}
```

**Response:**
```json
{
  "id": 1,
  "user_id": 123,
  "exchange_name": "binance",
  "label": "My Scalping Account",
  "status": "PENDING",
  "is_active": false,
  "error_message": null,
  "created_at": "2024-01-01T12:00:00",
  "updated_at": "2024-01-01T12:00:00"
}
```

#### GET `/user/exchanges/`
List all exchanges for the current user.

**Response:**
```json
[
  {
    "id": 1,
    "user_id": 123,
    "exchange_name": "binance",
    "label": "My Scalping Account",
    "status": "APPROVED",
    "is_active": true,
    "error_message": null,
    "created_at": "2024-01-01T12:00:00",
    "updated_at": "2024-01-01T12:00:00"
  }
]
```

#### PATCH `/user/exchanges/{exchange_id}/toggle`
Toggle exchange active status.

**Request:**
```json
{
  "is_active": true
}
```

**Note:** Can only set `is_active=true` if `status == 'APPROVED'`

### Admin Endpoints (`/admin/exchanges`)

#### GET `/admin/exchanges/pending`
List all pending exchange requests.

**Response:**
```json
[
  {
    "id": 1,
    "user_id": 123,
    "user_username": "user123",
    "user_email": "user@example.com",
    "exchange_name": "binance",
    "label": "My Scalping Account",
    "created_at": "2024-01-01T12:00:00"
  }
]
```

#### POST `/admin/exchanges/{exchange_id}/approve`
Approve an exchange request.

**Request:**
```json
{
  "notification_message": "Your exchange has been approved!"
}
```

#### POST `/admin/exchanges/{exchange_id}/reject`
Reject an exchange request.

**Request:**
```json
{
  "reason": "Invalid API credentials"
}
```

## Authentication

**Current Implementation:** HMAC-signed bearer tokens with expiration.

The authentication system uses secure HMAC-SHA256 signed tokens that include:
- User ID
- Timestamp (for expiration checking)
- HMAC signature (verified against server secret)

**Token Format:** `base64(user_id:timestamp:hmac_signature)`

**Security Features:**
- ✅ HMAC signature verification prevents token tampering
- ✅ 1-hour token expiration (configurable)
- ✅ Tokens are tied to user sessions
- ✅ Uses Flask's SECRET_KEY for signing

**Generating a Token:**

Tokens are automatically generated when a user logs into the Flask application. The token generation function is available in `security.py`:

```python
from security import generate_api_token

# Generate token for user
token = generate_api_token(user_id=123)
```

**Example Request:**
```bash
curl -X GET "http://localhost:8000/user/exchanges/" \
  -H "Authorization: Bearer <hmac_signed_token>"
```

**Token Verification Process:**
1. Decode base64 token
2. Extract user_id, timestamp, and signature
3. Verify token hasn't expired (1 hour max age)
4. Recompute HMAC signature and compare
5. Load user from database and verify active status

## Supported Exchanges

- Binance
- Bybit
- OKX (requires passphrase)
- Gate.io
- MEXC
- KuCoin (requires passphrase)
- Coinbase Pro
- Kraken

## Security Features

1. **Encryption**: All API secrets and passphrases are encrypted using Fernet symmetric encryption
2. **Validation**: Exchange credentials are validated immediately using CCXT before saving
3. **Approval Workflow**: Exchanges cannot be activated until admin approval
4. **Status Enforcement**: Users cannot activate exchanges with status != 'APPROVED'

## Database Schema

```sql
CREATE TABLE user_exchanges (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    exchange_name VARCHAR(50) NOT NULL,
    label VARCHAR(100) NOT NULL,
    api_key VARCHAR(500) NOT NULL,
    api_secret VARCHAR(500) NOT NULL,  -- Encrypted
    passphrase VARCHAR(500),            -- Encrypted (optional)
    status VARCHAR(20) DEFAULT 'PENDING',
    is_active BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    created_at DATETIME,
    updated_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

## Error Handling

All endpoints return standardized error responses:

```json
{
  "error": "Error message",
  "detail": "Detailed error information",
  "code": "400"
}
```

## Testing

Example using curl:

```bash
# Add exchange (requires authentication)
curl -X POST "http://localhost:8000/user/exchanges/" \
  -H "Authorization: Bearer 123" \
  -H "Content-Type: application/json" \
  -d '{
    "exchange_name": "binance",
    "api_key": "test_key",
    "api_secret": "test_secret",
    "label": "Test Account"
  }'

# List exchanges
curl -X GET "http://localhost:8000/user/exchanges/" \
  -H "Authorization: Bearer 123"

# Approve exchange (admin only)
curl -X POST "http://localhost:8000/admin/exchanges/1/approve" \
  -H "Authorization: Bearer 1" \
  -H "Content-Type: application/json" \
  -d '{"notification_message": "Approved!"}'
```

## Integration with Flask App

To integrate with the existing Flask app, you can:

1. Run FastAPI on a different port (e.g., 8000) alongside Flask (port 80)
2. Use a reverse proxy (nginx) to route `/api/exchanges/*` to FastAPI
3. Share the same database connection

Example nginx config:
```nginx
location /api/exchanges/ {
    proxy_pass http://localhost:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

## Next Steps

1. ~~**Implement proper JWT authentication**~~ ✅ Implemented (HMAC-signed tokens)
2. ~~**Add notification system**~~ ✅ Implemented (Telegram + Email notifications)
3. **Add exchange connection monitoring** - Periodic health checks
4. ~~**Add rate limiting**~~ ✅ Implemented (via FastAPI middleware)
5. **Add audit logging** - Track all exchange management actions
6. **Add exchange deletion** - Allow users to remove exchanges
7. **Add exchange update** - Allow users to update credentials

## Notes

- The system uses async/await for all CCXT operations
- All database operations should be wrapped in proper transaction handling
- In production, ensure proper error handling and logging
- Consider adding connection pooling for database connections
- Implement proper session management for FastAPI




