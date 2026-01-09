# Cloudflare Setup Guide for MIMIC

Complete guide to configuring Cloudflare for DNS, WAF, CDN, and Rate Limiting.

## Table of Contents
1. [Initial Setup](#1-initial-setup)
2. [DNS Configuration](#2-dns-configuration)
3. [SSL/TLS Settings](#3-ssltls-settings)
4. [CDN & Caching](#4-cdn--caching)
5. [WAF (Web Application Firewall)](#5-waf-web-application-firewall)
6. [Rate Limiting Rules](#6-rate-limiting-rules)
7. [Page Rules](#7-page-rules)
8. [DDoS Protection](#8-ddos-protection)
9. [Bot Management](#9-bot-management)
10. [Verification](#10-verification)

---

## 1. Initial Setup

### Add Domain to Cloudflare
1. Log in to [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Click **"Add a Site"**
3. Enter: `mimic.cash`
4. Select plan (Free tier works, Pro recommended for WAF)
5. Cloudflare will scan existing DNS records

### Update Nameservers
Update your domain registrar's nameservers to Cloudflare's:
```
ns1.cloudflare.com
ns2.cloudflare.com
```
*(Your actual nameservers will be shown in Cloudflare dashboard)*

---

## 2. DNS Configuration

### Required DNS Records

| Type | Name | Content | Proxy | TTL |
|------|------|---------|-------|-----|
| A | mimic.cash | YOUR_SERVER_IP | ✅ Proxied | Auto |
| A | api | YOUR_SERVER_IP | ✅ Proxied | Auto |
| CNAME | www | mimic.cash | ✅ Proxied | Auto |
| TXT | @ | v=spf1 include:_spf.google.com ~all | DNS only | Auto |
| MX | @ | mail.your-provider.com | DNS only | Auto |

### Important Notes
- **Orange Cloud (Proxied)**: Traffic goes through Cloudflare (CDN + Security)
- **Gray Cloud (DNS Only)**: Direct connection to your server
- Always proxy A/AAAA records for web traffic

---

## 3. SSL/TLS Settings

### Navigate to: SSL/TLS → Overview

#### Encryption Mode: **Full (Strict)**
```
Your Browser ←→ Cloudflare ←→ Your Server
     HTTPS          HTTPS (verified cert)
```

### SSL/TLS → Edge Certificates
- [x] **Always Use HTTPS**: ON
- [x] **Automatic HTTPS Rewrites**: ON
- [x] **TLS 1.3**: ON
- [x] **Minimum TLS Version**: TLS 1.2

### SSL/TLS → Origin Server
Generate an **Origin Certificate** (valid 15 years):
1. Click "Create Certificate"
2. Let Cloudflare generate private key
3. Hostnames: `mimic.cash`, `*.mimic.cash`
4. Validity: 15 years
5. Download and install on your server:
```bash
# Save certificate
sudo nano /etc/ssl/cloudflare/mimic.cash.pem

# Save private key
sudo nano /etc/ssl/cloudflare/mimic.cash.key

# Update nginx.conf to use these certs
ssl_certificate /etc/ssl/cloudflare/mimic.cash.pem;
ssl_certificate_key /etc/ssl/cloudflare/mimic.cash.key;
```

---

## 4. CDN & Caching

### Navigate to: Caching → Configuration

#### Caching Level: **Standard**

#### Browser Cache TTL: **Respect Existing Headers**
(Let Nginx control cache headers)

#### Crawler Hints: **ON**

### Caching → Cache Rules

#### Rule 1: Cache Static Assets Aggressively
```yaml
Name: Cache Static Assets
When: URI Path contains "/static/"
Then:
  - Cache eligibility: Eligible for cache
  - Edge TTL: 1 month
  - Browser TTL: 1 month
```

#### Rule 2: Bypass Cache for API
```yaml
Name: Bypass API Cache
When: URI Path starts with "/api/"
Then:
  - Cache eligibility: Bypass cache
```

#### Rule 3: Bypass Cache for WebSocket
```yaml
Name: Bypass WebSocket Cache
When: URI Path starts with "/socket.io/"
Then:
  - Cache eligibility: Bypass cache
```

#### Rule 4: Bypass Cache for Dashboard
```yaml
Name: Bypass Dashboard Cache
When: URI Path contains "/dashboard"
Then:
  - Cache eligibility: Bypass cache
```

---

## 5. WAF (Web Application Firewall)

### Navigate to: Security → WAF

### Managed Rules (Pro plan required)
Enable **Cloudflare Managed Ruleset**:
- [x] Cloudflare Managed Rules
- [x] Cloudflare OWASP Core Ruleset

### Custom Rules

#### Rule 1: Block Known Bad Bots
```
Name: Block Bad Bots
Expression:
(cf.client.bot) and not (cf.verified_bot_category in {"search_engine", "monitoring"})
Action: Block
```

#### Rule 2: Block SQL Injection Attempts
```
Name: Block SQLi
Expression:
(http.request.uri.query contains "UNION" and http.request.uri.query contains "SELECT") or
(http.request.uri.query contains "DROP" and http.request.uri.query contains "TABLE") or
(http.request.body.raw contains "UNION SELECT")
Action: Block
```

#### Rule 3: Block XSS Attempts
```
Name: Block XSS
Expression:
(http.request.uri.query contains "<script") or
(http.request.body.raw contains "<script") or
(http.request.uri.query contains "javascript:")
Action: Block
```

#### Rule 4: Protect Admin Routes
```
Name: Protect Admin
Expression:
(http.request.uri.path contains "/admin") and 
not (ip.src in {YOUR_ADMIN_IP/32})
Action: Managed Challenge
```

#### Rule 5: Block Suspicious User Agents
```
Name: Block Suspicious UA
Expression:
(http.user_agent contains "sqlmap") or
(http.user_agent contains "nikto") or
(http.user_agent contains "nmap") or
(http.user_agent eq "")
Action: Block
```

---

## 6. Rate Limiting Rules

### Navigate to: Security → WAF → Rate limiting rules

#### Rule 1: Login Rate Limit (Critical)
```yaml
Name: Login Rate Limit
Expression: (http.request.uri.path eq "/login") or 
            (http.request.uri.path eq "/api/login")
Characteristics:
  - IP address
Requests: 5 requests per 1 minute
Action: Block for 10 minutes
Response: Custom JSON
  {
    "error": "Too many login attempts. Please try again in 10 minutes.",
    "retry_after": 600
  }
```

#### Rule 2: Registration Rate Limit
```yaml
Name: Registration Rate Limit
Expression: (http.request.uri.path eq "/register") or 
            (http.request.uri.path eq "/api/register")
Characteristics:
  - IP address
Requests: 3 requests per 1 minute
Action: Block for 30 minutes
Response: Custom JSON
  {
    "error": "Too many registration attempts. Please try again later.",
    "retry_after": 1800
  }
```

#### Rule 3: Password Reset Rate Limit
```yaml
Name: Password Reset Rate Limit
Expression: (http.request.uri.path contains "forgot") or
            (http.request.uri.path contains "reset")
Characteristics:
  - IP address
Requests: 3 requests per 5 minutes
Action: Block for 15 minutes
```

#### Rule 4: API General Rate Limit
```yaml
Name: API Rate Limit
Expression: (http.request.uri.path starts with "/api/")
Characteristics:
  - IP address
Requests: 100 requests per 1 minute
Action: Block for 1 minute
```

#### Rule 5: Global Rate Limit (DDoS Prevention)
```yaml
Name: Global Rate Limit
Expression: (http.request.uri.path ne "/health")
Characteristics:
  - IP address
Requests: 500 requests per 1 minute
Action: Managed Challenge
```

---

## 7. Page Rules

### Navigate to: Rules → Page Rules

*(Free plan: 3 rules, Pro: 20 rules)*

#### Rule 1: Force HTTPS
```
URL: http://*mimic.cash/*
Settings:
  - Always Use HTTPS: ON
```

#### Rule 2: Cache Everything for Static
```
URL: *mimic.cash/static/*
Settings:
  - Cache Level: Cache Everything
  - Edge Cache TTL: 1 month
  - Browser Cache TTL: 1 month
```

#### Rule 3: Bypass for API
```
URL: *mimic.cash/api/*
Settings:
  - Cache Level: Bypass
  - Disable Performance
  - Disable Security: OFF (keep security!)
```

---

## 8. DDoS Protection

### Navigate to: Security → DDoS

#### L7 DDoS Attack Protection
- **Ruleset action**: Block
- **Ruleset sensitivity**: High

### Security → Settings
- **Security Level**: High
- **Challenge Passage**: 30 minutes
- **Browser Integrity Check**: ON

---

## 9. Bot Management

### Navigate to: Security → Bots

#### Bot Fight Mode: **ON**
*(Free feature - blocks known bad bots)*

#### Super Bot Fight Mode (Pro):
- **Definitely Automated**: Block
- **Likely Automated**: Managed Challenge
- **Verified Bots**: Allow
- **Static resource protection**: ON
- **JavaScript Detections**: ON

---

## 10. Verification

### Test SSL
```bash
curl -I https://mimic.cash
# Should show: HTTP/2 200
# Should show: cf-ray header (Cloudflare)
```

### Test Rate Limiting
```bash
# Test login rate limit (should get 429 after 5 requests)
for i in {1..10}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST https://mimic.cash/api/login \
    -d "username=test&password=test"
done
```

### Verify Cloudflare Headers
```bash
curl -I https://mimic.cash 2>/dev/null | grep -i cf-
# Should show:
# cf-ray: xxxxx-XXX
# cf-cache-status: DYNAMIC or HIT
```

### Test WAF
```bash
# This should be blocked
curl "https://mimic.cash/?id=1' UNION SELECT * FROM users--"
# Should return 403 or challenge page
```

---

## Quick Reference: Cloudflare IP Ranges

For Nginx `set_real_ip_from` configuration:

```nginx
# IPv4
set_real_ip_from 103.21.244.0/22;
set_real_ip_from 103.22.200.0/22;
set_real_ip_from 103.31.4.0/22;
set_real_ip_from 104.16.0.0/13;
set_real_ip_from 104.24.0.0/14;
set_real_ip_from 108.162.192.0/18;
set_real_ip_from 131.0.72.0/22;
set_real_ip_from 141.101.64.0/18;
set_real_ip_from 162.158.0.0/15;
set_real_ip_from 172.64.0.0/13;
set_real_ip_from 173.245.48.0/20;
set_real_ip_from 188.114.96.0/20;
set_real_ip_from 190.93.240.0/20;
set_real_ip_from 197.234.240.0/22;
set_real_ip_from 198.41.128.0/17;

# IPv6
set_real_ip_from 2400:cb00::/32;
set_real_ip_from 2606:4700::/32;
set_real_ip_from 2803:f800::/32;
set_real_ip_from 2405:b500::/32;
set_real_ip_from 2405:8100::/32;
set_real_ip_from 2a06:98c0::/29;
set_real_ip_from 2c0f:f248::/32;

real_ip_header CF-Connecting-IP;
```

Update these from: https://www.cloudflare.com/ips/

---

## Firewall Rules (Server Level)

Once Cloudflare is set up, restrict server access to Cloudflare IPs only:

```bash
# UFW (Ubuntu)
# IMPORTANT: Allow SSH first to avoid lockout!
sudo ufw allow ssh

sudo ufw default deny incoming

# Allow all Cloudflare IP ranges (download current list)
for ip in $(curl -s https://www.cloudflare.com/ips-v4); do
  sudo ufw allow from $ip to any port 443
done
for ip in $(curl -s https://www.cloudflare.com/ips-v6); do
  sudo ufw allow from $ip to any port 443
done

sudo ufw enable

# Or use iptables script
wget -q https://www.cloudflare.com/ips-v4 -O /tmp/cf-ips-v4
wget -q https://www.cloudflare.com/ips-v6 -O /tmp/cf-ips-v6
for ip in $(cat /tmp/cf-ips-v4); do
  iptables -A INPUT -p tcp -s $ip --dport 443 -j ACCEPT
done
iptables -A INPUT -p tcp --dport 443 -j DROP
```

---

## Summary Checklist

- [ ] Domain added to Cloudflare
- [ ] Nameservers updated at registrar
- [ ] DNS records configured (A, CNAME proxied)
- [ ] SSL mode: Full (Strict)
- [ ] Origin certificate installed
- [ ] Always Use HTTPS: ON
- [ ] TLS 1.3: ON
- [ ] Cache rules configured
- [ ] WAF managed rules enabled
- [ ] Custom WAF rules added
- [ ] Rate limiting rules configured
- [ ] Bot protection enabled
- [ ] Server firewall restricts to Cloudflare IPs
- [ ] Tested and verified

---

## Support Resources

- [Cloudflare Documentation](https://developers.cloudflare.com/)
- [Cloudflare Community](https://community.cloudflare.com/)
- [Status Page](https://www.cloudflarestatus.com/)
- [IP Ranges](https://www.cloudflare.com/ips/)
