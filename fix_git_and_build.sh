#!/bin/bash
#
# Fix git conflict and rebuild frontend
# ====================================

set -e

INSTALL_PATH="/var/www/mimic"

echo "🔧 Fixing git conflict and rebuilding frontend..."
echo ""

cd "$INSTALL_PATH"

# ============================================================================
# STEP 1: Resolve Git Conflict
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 1: Resolving Git Conflict"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if there are local changes
if git diff --quiet fix_frontend_design.sh 2>/dev/null; then
    echo "✅ No local changes to fix_frontend_design.sh"
else
    echo "⚠️  Local changes detected in fix_frontend_design.sh"
    echo "Stashing local changes..."
    git stash push -m "Stash local fix_frontend_design.sh changes before pull" fix_frontend_design.sh
    echo "✅ Changes stashed"
fi

# Pull latest changes
echo ""
echo "Pulling latest changes from repository..."
git pull

# ============================================================================
# STEP 2: Ensure tailwind.input.css exists
# ============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 2: Ensuring tailwind.input.css exists"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Create directory if it doesn't exist
mkdir -p "$INSTALL_PATH/static/css"

# Create tailwind.input.css if it doesn't exist
TAILWIND_INPUT="$INSTALL_PATH/static/css/tailwind.input.css"
if [[ ! -f "$TAILWIND_INPUT" ]]; then
    echo "Creating tailwind.input.css..."
    cat > "$TAILWIND_INPUT" << 'EOF'
@tailwind base;
@tailwind components;
@tailwind utilities;

/* Custom styles can be added here */
EOF
    echo "✅ Created tailwind.input.css at $TAILWIND_INPUT"
else
    echo "✅ tailwind.input.css already exists"
fi

# Verify file exists and show its location
if [[ -f "$TAILWIND_INPUT" ]]; then
    echo "   File location: $TAILWIND_INPUT"
    echo "   File size: $(stat -f%z "$TAILWIND_INPUT" 2>/dev/null || stat -c%s "$TAILWIND_INPUT" 2>/dev/null || echo "unknown") bytes"
else
    echo "❌ Failed to create tailwind.input.css!"
    exit 1
fi

# ============================================================================
# STEP 3: Rebuild Frontend
# ============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 3: Rebuilding Frontend"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Ensure we're in the right directory
cd "$INSTALL_PATH"

# Check if package.json exists
if [[ ! -f "$INSTALL_PATH/package.json" ]]; then
    echo "❌ package.json not found!"
    exit 1
fi

# Check if node_modules exists
if [[ ! -d "$INSTALL_PATH/node_modules" ]]; then
    echo "Installing Node.js dependencies..."
    npm install
else
    echo "✅ node_modules exists"
fi

# Verify tailwind.input.css exists from current directory
if [[ ! -f "./static/css/tailwind.input.css" ]]; then
    echo "❌ tailwind.input.css not found at ./static/css/tailwind.input.css"
    echo "   Current directory: $(pwd)"
    echo "   Looking for: $(pwd)/static/css/tailwind.input.css"
    exit 1
fi

# Rebuild CSS
echo ""
echo "Rebuilding CSS (this may take a minute)..."
npm run build

if [[ $? -eq 0 ]]; then
    echo "✅ Frontend build successful"
else
    echo "❌ Frontend build failed"
    exit 1
fi

# ============================================================================
# STEP 4: Restart Services
# ============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 4: Restarting Services"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Reload Nginx
sudo systemctl reload nginx
echo "✅ Nginx reloaded"

# Restart mimic
sudo systemctl restart mimic
sleep 3

if systemctl is-active --quiet mimic; then
    echo "✅ mimic.service restarted successfully"
else
    echo "❌ mimic.service failed to restart"
    exit 1
fi

echo ""
echo "✅ All fixes complete!"
echo ""
echo "Next steps:"
echo "  1. Clear browser cache (Ctrl+Shift+R or Cmd+Shift+R)"
echo "  2. Test website: https://mimiccash.com"
echo "  3. Check browser console for errors (F12)"
echo ""
