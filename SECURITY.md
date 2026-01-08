# MIMIC Trading Platform - Security Guide

## 🔒 Security Features Implemented

### 1. Authentication & Session Security

- **Strong Password Policy**: Minimum 8 characters with uppercase, lowercase, and numbers
- **Session Fingerprinting**: Detects session hijacking via browser fingerprint validation
- **Secure Session Cookies**: HttpOnly, SameSite=Strict, Secure (in production)
- **Session Timeout**: 8-hour automatic expiration
- **Login Rate Limiting**: Max 10 attempts per minute per IP
- **Failed Login Tracking**: IP blocking after 5 failed attempts

### 2. CSRF Protection

- All POST forms include CSRF tokens
- Token validation on all sensitive endpoints
- Tokens expire after 1 hour

### 3. Input Validation & Sanitization

- SQL injection pattern detection and blocking
- XSS pattern detection and blocking
- HTML entity escaping for user inputs
- Username/password format validation
- API key format validation

### 4. API Security (FastAPI)

- CORS restricted to specific origins (not `*`)
- Security headers middleware (X-Frame-Options, CSP, etc.)
- Rate limiting middleware (100 requests/minute)
- HMAC-signed API tokens with 1-hour expiration
- Token signature verification

### 5. Data Protection

- API keys encrypted with Fernet symmetric encryption
- Passwords hashed with scrypt algorithm
- Sensitive data masked in logs
- No debug information exposed to clients

### 6. Security Headers

All responses include:
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Content-Security-Policy` (restrictive policy)
- `Permissions-Policy` (disabled geolocation, camera, microphone)

### 7. Rate Limiting

- Login: 10 requests/minute
- Registration: 3 requests/hour
- Webhooks: 30 requests/minute
- General API: 100 requests/minute

---

## ⚠️ Security Best Practices

### Configuration

1. **NEVER commit `config.ini` to version control**
   - Use `config.ini.secure` as a template
   - Add `config.ini` to `.gitignore`

2. **Set environment variables for secrets**:
   ```bash
   export FLASK_SECRET_KEY="your-very-long-random-secret-key"
   export BRAIN_CAPITAL_MASTER_KEY="your-fernet-key"
   export FLASK_ENV="production"
   ```

3. **Generate secure keys**:
   ```python
   # For FLASK_SECRET_KEY
   import secrets
   print(secrets.token_hex(32))
   
   # For BRAIN_CAPITAL_MASTER_KEY (Fernet)
   from cryptography.fernet import Fernet
   print(Fernet.generate_key().decode())
   ```

### Production Deployment

1. **Enable HTTPS**:
   - Set `SESSION_COOKIE_SECURE=True`
   - Use a reverse proxy (nginx) with SSL

2. **Update CORS origins**:
   - In `app_fastapi.py`: Update `ALLOWED_ORIGINS`
   - In `app.py`: Set `ALLOWED_ORIGINS` environment variable

3. **Database Security**:
   - Use PostgreSQL instead of SQLite
   - Enable connection pooling
   - Use encrypted connections

4. **File Permissions**:
   ```bash
   chmod 600 config.ini
   chmod 700 static/avatars
   ```

### Monitoring

1. **Check security logs regularly**:
   - Failed login attempts
   - CSRF validation failures
   - SQL/XSS injection attempts
   - Admin actions

2. **Monitor blocked IPs**:
   - Use `/admin/security/status` endpoint

---

## 🚨 Security Incident Response

### If API Keys Are Compromised

1. Immediately revoke the keys on the exchange
2. Generate new keys
3. Update encrypted storage
4. Review access logs
5. Notify affected users

### If Session Is Hijacked

1. Force logout all sessions
2. Reset user password
3. Review access logs
4. Check for XSS vulnerabilities

### If Database Is Compromised

1. Take system offline
2. Assess damage
3. Reset all passwords
4. Re-encrypt all API keys with new master key
5. Notify users

---

## 📋 Security Checklist

Before going to production:

- [ ] All API keys removed from `config.ini`
- [ ] `config.ini` added to `.gitignore`
- [ ] `FLASK_ENV=production` set
- [ ] `SESSION_COOKIE_SECURE=True`
- [ ] HTTPS configured
- [ ] CORS origins updated
- [ ] Database credentials secure
- [ ] Logs do not contain sensitive data
- [ ] Rate limiting tested
- [ ] CSRF protection verified
- [ ] Password policy enforced
- [ ] Security headers present

---

## 🔧 Testing Security

### Test CSRF Protection
```bash
curl -X POST http://localhost:5000/login \
  -d "username=test&password=test" \
  -H "Content-Type: application/x-www-form-urlencoded"
# Should return 403 Forbidden
```

### Test Rate Limiting
```bash
for i in {1..15}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST http://localhost:5000/login \
    -d "username=test&password=wrong"
done
# Should eventually return 429
```

### Test Security Headers
```bash
curl -I http://localhost:5000/
# Check for security headers in response
```

---

## 📞 Reporting Security Issues

If you discover a security vulnerability, please:
1. Do NOT create a public issue
2. Email the security team directly
3. Include details of the vulnerability
4. Allow time for a fix before disclosure

