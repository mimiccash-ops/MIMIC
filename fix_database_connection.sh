#!/bin/bash
#
# Fix database connection issues
# ==============================
#

set -e

INSTALL_PATH="/var/www/mimic"

echo "🔧 Fixing database connection..."
echo ""

cd "$INSTALL_PATH"

# ============================================================================
# STEP 1: Check current DATABASE_URL
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 1: Checking DATABASE_URL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if grep -q "^DATABASE_URL=" .env; then
    DB_URL=$(grep "^DATABASE_URL=" .env | cut -d'=' -f2- | head -1)
    echo "Current DATABASE_URL: ${DB_URL:0:80}..."
    
    # Extract components
    if echo "$DB_URL" | grep -q "mimic_user"; then
        echo "✅ Using mimic_user"
        DB_USER="mimic_user"
        DB_NAME="mimic_db"
        
        # Extract password from URL
        DB_PASSWORD=$(echo "$DB_URL" | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
        if [[ -n "$DB_PASSWORD" ]]; then
            echo "✅ Password found in DATABASE_URL"
        else
            echo "⚠️  Could not extract password from DATABASE_URL"
        fi
    elif echo "$DB_URL" | grep -q "brain_capital"; then
        echo "✅ Using brain_capital (Docker)"
        DB_USER="brain_capital"
        DB_NAME="brain_capital"
    else
        echo "⚠️  Unknown database user in DATABASE_URL"
    fi
else
    echo "❌ DATABASE_URL not found in .env"
    exit 1
fi

echo ""

# ============================================================================
# STEP 2: Check if using Docker or local PostgreSQL
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 2: Checking Database Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if Docker PostgreSQL is running
if docker compose ps db 2>/dev/null | grep -q "Up.*healthy"; then
    echo "✅ Docker PostgreSQL is running and healthy"
    USE_DOCKER_DB=true
else
    echo "⚠️  Docker PostgreSQL is not running"
    USE_DOCKER_DB=false
fi

# Check if local PostgreSQL is running
if systemctl is-active --quiet postgresql 2>/dev/null; then
    echo "✅ Local PostgreSQL service is running"
    USE_LOCAL_DB=true
else
    echo "⚠️  Local PostgreSQL service is not running"
    USE_LOCAL_DB=false
fi

echo ""

# ============================================================================
# STEP 3: Fix Database Connection
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 3: Fixing Database Connection"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Option 1: Use Docker database (recommended if Docker is running)
if [[ "$USE_DOCKER_DB" == "true" ]]; then
    echo "Using Docker database (recommended)..."
    
    # Get Docker database password from .env or docker-compose
    DOCKER_DB_PASSWORD=$(grep "POSTGRES_PASSWORD=" .env 2>/dev/null | cut -d'=' -f2 | head -1 || echo "")
    
    if [[ -z "$DOCKER_DB_PASSWORD" ]]; then
        echo "⚠️  POSTGRES_PASSWORD not found in .env"
        echo "   Checking docker-compose.yml..."
        # Try to get from docker-compose.yml (if using variable)
        DOCKER_DB_PASSWORD=$(grep "POSTGRES_PASSWORD" docker-compose.yml 2>/dev/null | head -1 || echo "")
    fi
    
    # Update DATABASE_URL to use Docker database
    echo "Updating DATABASE_URL to use Docker database..."
    sed -i '/^DATABASE_URL=/d' .env
    
    if [[ -n "$DOCKER_DB_PASSWORD" ]]; then
        echo "DATABASE_URL=postgresql://brain_capital:${DOCKER_DB_PASSWORD}@localhost:5432/brain_capital" >> .env
        echo "✅ Updated DATABASE_URL to use Docker database"
    else
        echo "⚠️  Could not determine Docker database password"
        echo "   Please set POSTGRES_PASSWORD in .env or update DATABASE_URL manually"
    fi
else
    # Option 2: Fix local PostgreSQL password
    if [[ "$USE_LOCAL_DB" == "true" ]] && [[ "$DB_USER" == "mimic_user" ]]; then
        echo "Fixing local PostgreSQL password..."
        
        if [[ -n "$DB_PASSWORD" ]]; then
            echo "Setting password for mimic_user..."
            sudo -u postgres psql << EOF > /dev/null 2>&1
ALTER USER mimic_user WITH PASSWORD '$DB_PASSWORD';
\q
EOF
            if [[ $? -eq 0 ]]; then
                echo "✅ Password updated for mimic_user"
            else
                echo "⚠️  Could not update password (user may not exist)"
                echo "   Creating user and database..."
                sudo -u postgres psql << EOF > /dev/null 2>&1
CREATE USER mimic_user WITH PASSWORD '$DB_PASSWORD';
CREATE DATABASE mimic_db OWNER mimic_user;
GRANT ALL PRIVILEGES ON DATABASE mimic_db TO mimic_user;
\q
EOF
                echo "✅ User and database created"
            fi
        else
            echo "⚠️  Could not extract password from DATABASE_URL"
            echo "   Please set password manually:"
            echo "   sudo -u postgres psql -c \"ALTER USER mimic_user WITH PASSWORD 'your_password';\""
        fi
    else
        echo "⚠️  Cannot determine database setup"
        echo "   Please check DATABASE_URL in .env"
    fi
fi

echo ""

# ============================================================================
# STEP 4: Test Connection
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 4: Testing Database Connection"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Test connection
if python3 -c "
import os
import sys
sys.path.insert(0, '$INSTALL_PATH')
from app import app, db
with app.app_context():
    try:
        conn = db.engine.connect()
        result = conn.execute(db.text('SELECT 1'))
        print('✅ Database connection successful!')
        conn.close()
    except Exception as e:
        print(f'❌ Database connection failed: {e}')
        sys.exit(1)
" 2>/dev/null; then
    echo "✅ Database connection test passed"
else
    echo "❌ Database connection test failed"
    echo ""
    echo "Current DATABASE_URL:"
    grep "^DATABASE_URL=" .env | head -1
    echo ""
    echo "Please check:"
    echo "  1. Database is running (Docker or local)"
    echo "  2. DATABASE_URL is correct in .env"
    echo "  3. Password matches database user"
fi

echo ""

# ============================================================================
# STEP 5: Restart Services
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 5: Restarting Services"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Restarting mimic service..."
sudo systemctl restart mimic
sleep 3

if systemctl is-active --quiet mimic; then
    echo "✅ mimic.service restarted successfully"
else
    echo "❌ mimic.service failed to start"
    echo "   Check logs: sudo journalctl -u mimic -n 50"
fi

echo ""
echo "✅ Database connection fix complete!"
echo ""
echo "Test the website:"
echo "  curl https://mimiccash.com/health"
echo ""
