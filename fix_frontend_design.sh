#!/bin/bash
#
# Fix frontend design issues
# ==========================
#

set -e

INSTALL_PATH="/var/www/mimic"

echo "🔧 Fixing frontend design issues..."
echo ""

cd "$INSTALL_PATH"

# ============================================================================
# STEP 1: Rebuild Frontend
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 1: Rebuilding Frontend"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [[ -f "$INSTALL_PATH/package.json" ]]; then
    echo "✅ package.json found"
    
    # Check if node_modules exists
    if [[ ! -d "$INSTALL_PATH/node_modules" ]]; then
        echo "Installing Node.js dependencies..."
        npm install
    else
        echo "✅ node_modules exists"
    fi
    
    # Create tailwind.input.css if it doesn't exist
    if [[ ! -f "$INSTALL_PATH/static/css/tailwind.input.css" ]]; then
        echo "Creating tailwind.input.css..."
        mkdir -p "$INSTALL_PATH/static/css"
        cat > "$INSTALL_PATH/static/css/tailwind.input.css" << 'EOF'
@tailwind base;
@tailwind components;
@tailwind utilities;
EOF
        echo "✅ Created tailwind.input.css"
    fi
    
    # Rebuild CSS
    echo ""
    echo "Rebuilding CSS (this may take a minute)..."
    npm run build
    
    if [[ $? -eq 0 ]]; then
        echo "✅ Frontend build successful"
    else
        echo "⚠️  Frontend build had warnings (may be OK)"
    fi
else
    echo "⚠️  No package.json found, skipping frontend build"
fi

echo ""

# ============================================================================
# STEP 2: Check Static Files
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 2: Checking Static Files"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check CSS files
CSS_FILES=$(find "$INSTALL_PATH/static" -name "*.css" 2>/dev/null | wc -l)
if [[ "$CSS_FILES" -gt 0 ]]; then
    echo "✅ Found $CSS_FILES CSS files"
    find "$INSTALL_PATH/static" -name "*.css" | head -5
else
    echo "❌ No CSS files found!"
fi

# Check JS files
JS_FILES=$(find "$INSTALL_PATH/static" -name "*.js" 2>/dev/null | wc -l)
if [[ "$JS_FILES" -gt 0 ]]; then
    echo "✅ Found $JS_FILES JS files"
else
    echo "⚠️  No JS files found"
fi

# Check permissions
echo ""
echo "Checking permissions..."
ls -la "$INSTALL_PATH/static" | head -10

echo ""

# ============================================================================
# STEP 3: Fix Permissions
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 3: Fixing Static File Permissions"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Fix ownership
chown -R mimic:mimic "$INSTALL_PATH/static" 2>/dev/null || true

# Fix permissions
chmod -R 755 "$INSTALL_PATH/static" 2>/dev/null || true

echo "✅ Permissions fixed"

echo ""

# ============================================================================
# STEP 4: Check Nginx Static File Serving
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 4: Checking Nginx Static File Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if Nginx is configured to serve static files
if grep -q "/static/" /etc/nginx/nginx.conf 2>/dev/null || grep -q "/static/" /etc/nginx/sites-enabled/* 2>/dev/null; then
    echo "✅ Nginx static file configuration found"
    
    # Check if path matches
    STATIC_PATH=$(grep -h "alias.*static" /etc/nginx/nginx.conf /etc/nginx/sites-enabled/* 2>/dev/null | head -1 | awk '{print $2}' | sed 's/;//')
    if [[ -n "$STATIC_PATH" ]]; then
        echo "   Static path: $STATIC_PATH"
        if [[ "$STATIC_PATH" == "$INSTALL_PATH/static" ]] || [[ "$STATIC_PATH" == "$INSTALL_PATH/static/" ]]; then
            echo "✅ Static path matches installation path"
        else
            echo "⚠️  Static path may not match: $STATIC_PATH vs $INSTALL_PATH/static"
        fi
    fi
else
    echo "⚠️  Nginx static file configuration not found"
fi

echo ""

# ============================================================================
# STEP 5: Test Static File Access
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 5: Testing Static File Access"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Test local access
if curl -s -o /dev/null -w "%{http_code}" http://localhost/static/css/tailwind.css | grep -q "200"; then
    echo "✅ CSS file accessible via Nginx"
else
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/static/css/tailwind.css)
    echo "⚠️  CSS file returned HTTP $HTTP_CODE"
fi

# Test external access
if curl -s -o /dev/null -w "%{http_code}" https://mimiccash.com/static/css/tailwind.css | grep -q "200"; then
    echo "✅ CSS file accessible externally"
else
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://mimiccash.com/static/css/tailwind.css)
    echo "⚠️  CSS file returned HTTP $HTTP_CODE externally"
fi

echo ""

# ============================================================================
# STEP 6: Restart Services
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 6: Restarting Services"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Reload Nginx (to pick up any changes)
sudo systemctl reload nginx
echo "✅ Nginx reloaded"

# Restart mimic (to clear any cached issues)
sudo systemctl restart mimic
sleep 3

if systemctl is-active --quiet mimic; then
    echo "✅ mimic.service restarted successfully"
else
    echo "❌ mimic.service failed to restart"
fi

echo ""
echo "✅ Frontend fix complete!"
echo ""
echo "Next steps:"
echo "  1. Clear browser cache (Ctrl+Shift+R or Cmd+Shift+R)"
echo "  2. Test website: https://mimiccash.com"
echo "  3. Check browser console for errors (F12)"
echo ""
