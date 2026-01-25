#!/bin/bash
#
# Fix Nginx SSL and Gunicorn issues
# =================================
#

set -e

INSTALL_PATH="/var/www/mimic"

echo "🔧 Fixing Nginx SSL and Gunicorn issues..."
echo ""

cd "$INSTALL_PATH"

# ============================================================================
# STEP 1: Check Gunicorn status and logs
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 1: Checking Gunicorn status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if systemctl is-active --quiet mimic; then
    echo "✅ MIMIC service is running"
else
    echo "❌ MIMIC service is NOT running"
    echo ""
    echo "Checking logs..."
    sudo journalctl -u mimic -n 50 --no-pager
    echo ""
    echo "Attempting to start..."
    sudo systemctl start mimic || true
    sleep 2
    if systemctl is-active --quiet mimic; then
        echo "✅ MIMIC service started"
    else
        echo "❌ MIMIC service failed to start. Check logs above."
    fi
fi

# Check if Gunicorn is listening on port 8000
if sudo ss -tlnp | grep -q ":8000"; then
    echo "✅ Gunicorn is listening on port 8000"
    sudo ss -tlnp | grep ":8000"
else
    echo "❌ Gunicorn is NOT listening on port 8000"
    echo ""
    echo "Checking what's listening on port 8000..."
    sudo lsof -i :8000 || echo "Nothing listening on port 8000"
fi

echo ""

# ============================================================================
# STEP 2: Check SSL certificates
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 2: Checking SSL certificates"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

SSL_CERT="/etc/letsencrypt/live/mimiccash.com/fullchain.pem"
SSL_KEY="/etc/letsencrypt/live/mimiccash.com/privkey.pem"

if [[ -f "$SSL_CERT" ]] && [[ -f "$SSL_KEY" ]]; then
    echo "✅ SSL certificates found"
    echo "   Certificate: $SSL_CERT"
    echo "   Key: $SSL_KEY"
    SSL_AVAILABLE=true
else
    echo "⚠️  SSL certificates NOT found"
    echo "   Expected: $SSL_CERT"
    echo "   Expected: $SSL_KEY"
    SSL_AVAILABLE=false
fi

echo ""

# ============================================================================
# STEP 3: Create temporary HTTP-only Nginx config if SSL is missing
# ============================================================================
if [[ "$SSL_AVAILABLE" == "false" ]]; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "STEP 3: Creating HTTP-only Nginx configuration"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Backup current config
    if [[ -f /etc/nginx/nginx.conf ]]; then
        sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup.$(date +%Y%m%d_%H%M%S)
        echo "✅ Backed up current Nginx config"
    fi
    
    # Create HTTP-only config
    cat > /tmp/nginx_http_only.conf << 'NGINX_EOF'
# HTTP-only Nginx configuration (no SSL)
# This is a temporary configuration until SSL certificates are installed

user www-data;
worker_processes auto;
worker_rlimit_nofile 65535;

error_log /var/log/nginx/error.log warn;
pid /run/nginx.pid;

events {
    worker_connections 4096;
    use epoll;
    multi_accept on;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    
    keepalive_timeout 65;
    keepalive_requests 1000;
    
    client_body_buffer_size 16K;
    client_header_buffer_size 1k;
    client_max_body_size 16M;
    large_client_header_buffers 4 32k;
    
    client_body_timeout 30s;
    client_header_timeout 30s;
    send_timeout 30s;
    
    types_hash_max_size 2048;
    server_names_hash_bucket_size 64;

    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_buffers 16 8k;
    gzip_http_version 1.1;
    gzip_min_length 256;
    gzip_types
        application/javascript
        application/json
        application/xml
        text/css
        text/javascript
        text/plain
        text/xml;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Upstream - Flask/Gunicorn Backend
    upstream mimic_backend {
        server 127.0.0.1:8000;
        keepalive 32;
        keepalive_requests 1000;
        keepalive_timeout 60s;
    }

    # HTTP Server (port 80)
    server {
        listen 80;
        listen [::]:80;
        server_name mimiccash.com www.mimiccash.com;

        # Health check
        location = /health {
            access_log off;
            return 200 "OK";
            add_header Content-Type text/plain;
        }

        # ACME challenge for Let's Encrypt
        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        # WebSocket - Socket.IO
        location /socket.io/ {
            proxy_pass http://mimic_backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 86400s;
            proxy_send_timeout 86400s;
            proxy_connect_timeout 60s;
            proxy_buffering off;
        }

        # TradingView Webhook (no rate limiting)
        location = /webhook {
            proxy_pass http://mimic_backend;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Connection "";
            proxy_connect_timeout 60s;
            proxy_read_timeout 120s;
            proxy_send_timeout 60s;
            proxy_request_buffering off;
            proxy_buffering off;
        }

        # Static files
        location /static/ {
            alias /var/www/mimic/static/;
            expires 30d;
            add_header Cache-Control "public, no-transform, immutable";
            access_log off;
        }

        # Service Worker
        location = /service-worker.js {
            alias /var/www/mimic/static/service-worker.js;
            expires -1;
            add_header Cache-Control "no-store, no-cache, must-revalidate";
            add_header Service-Worker-Allowed "/";
        }

        # Favicon
        location = /favicon.ico {
            alias /var/www/mimic/static/icons/favicon.ico;
            expires 30d;
            access_log off;
        }

        # Robots.txt
        location = /robots.txt {
            alias /var/www/mimic/static/robots.txt;
            expires 1d;
            access_log off;
        }

        # Main application
        location / {
            proxy_pass http://mimic_backend;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Forwarded-Host $host;
            proxy_set_header Connection "";
            
            proxy_connect_timeout 30s;
            proxy_read_timeout 60s;
            proxy_send_timeout 30s;
            
            proxy_buffering on;
            proxy_buffer_size 4k;
            proxy_buffers 8 4k;
        }

        # Deny sensitive files
        location ~ /\. {
            deny all;
            access_log off;
            log_not_found off;
        }
        
        location ~ \.(ini|env|log|sql|bak)$ {
            deny all;
            access_log off;
            log_not_found off;
        }
    }
}
NGINX_EOF

    echo "✅ Created HTTP-only Nginx configuration"
    echo ""
    echo "Installing HTTP-only config..."
    sudo cp /tmp/nginx_http_only.conf /etc/nginx/nginx.conf
    echo "✅ Installed HTTP-only Nginx configuration"
    echo ""
    echo "⚠️  NOTE: This is a temporary HTTP-only configuration."
    echo "   To enable HTTPS, install SSL certificates:"
    echo "   sudo certbot --nginx -d mimiccash.com -d www.mimiccash.com"
    echo ""
fi

# ============================================================================
# STEP 4: Test and reload Nginx
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 4: Testing and reloading Nginx"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if sudo nginx -t; then
    echo "✅ Nginx configuration is valid"
    echo ""
    echo "Reloading Nginx..."
    sudo systemctl reload nginx
    echo "✅ Nginx reloaded"
else
    echo "❌ Nginx configuration has errors"
    sudo nginx -t
    exit 1
fi

echo ""
echo "✅ All fixes applied!"
echo ""
echo "Next steps:"
echo "  1. Test Gunicorn: curl http://localhost:8000/health"
echo "  2. Test Nginx: curl http://localhost/health"
echo "  3. Check Gunicorn logs: sudo journalctl -u mimic -f"
echo "  4. Check Nginx logs: sudo tail -f /var/log/nginx/error.log"
echo ""
if [[ "$SSL_AVAILABLE" == "false" ]]; then
    echo "  5. Install SSL certificates:"
    echo "     sudo certbot --nginx -d mimiccash.com -d www.mimiccash.com"
    echo "     (After SSL is installed, restore nginx.conf.production)"
fi
echo ""
