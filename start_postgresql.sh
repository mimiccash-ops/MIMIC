#!/bin/bash
#
# Start PostgreSQL and check status
#

echo "🔍 Checking PostgreSQL status..."

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "❌ PostgreSQL is not installed!"
    echo "Install it with: sudo apt install postgresql postgresql-contrib"
    exit 1
fi

# Check if PostgreSQL is running
if systemctl is-active --quiet postgresql; then
    echo "✅ PostgreSQL is already running"
else
    echo "ℹ️  Starting PostgreSQL..."
    sudo systemctl start postgresql
    
    # Wait a moment for it to start
    sleep 2
    
    if systemctl is-active --quiet postgresql; then
        echo "✅ PostgreSQL started successfully"
    else
        echo "❌ Failed to start PostgreSQL"
        echo "Check status with: sudo systemctl status postgresql"
        exit 1
    fi
fi

# Enable PostgreSQL to start on boot
sudo systemctl enable postgresql

# Check connection
echo ""
echo "🔍 Testing database connection..."
if sudo -u postgres psql -c "SELECT version();" &> /dev/null; then
    echo "✅ PostgreSQL connection successful"
else
    echo "⚠️  Could not connect to PostgreSQL"
    echo "Try: sudo systemctl restart postgresql"
fi

echo ""
echo "📊 PostgreSQL Status:"
sudo systemctl status postgresql --no-pager -l | head -10
