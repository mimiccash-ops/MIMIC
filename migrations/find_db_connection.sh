#!/bin/bash
# Script to find database connection details

echo "=== Checking for Database Connection Details ==="
echo ""

# Check environment variables
echo "1. Environment variables:"
if [ -n "$DATABASE_URL" ]; then
    echo "   DATABASE_URL found: ${DATABASE_URL/@*/@***}"
else
    echo "   DATABASE_URL not set"
fi
echo ""

# Check config.ini
echo "2. Checking config.ini:"
if [ -f "config.ini" ]; then
    echo "   config.ini exists"
    if grep -q "DATABASE_URL" config.ini; then
        echo "   DATABASE_URL found in config.ini"
        grep "DATABASE_URL" config.ini | sed 's/.*DATABASE_URL.*/   &/'
    fi
    if grep -q "\[Database\]" config.ini; then
        echo "   [Database] section found:"
        sed -n '/\[Database\]/,/\[/p' config.ini | grep -v "^\[" | sed 's/^/   /'
    fi
else
    echo "   config.ini not found"
fi
echo ""

# Check .env files
echo "3. Checking .env files:"
if [ -f ".env" ]; then
    echo "   .env file exists"
    if grep -q "DATABASE_URL" .env; then
        echo "   DATABASE_URL found in .env:"
        grep "DATABASE_URL" .env | sed 's/password=[^@]*/password=***/g' | sed 's/^/   /'
    fi
fi
if [ -f "production.env" ]; then
    echo "   production.env file exists"
    if grep -q "DATABASE_URL" production.env; then
        echo "   DATABASE_URL found in production.env:"
        grep "DATABASE_URL" production.env | sed 's/password=[^@]*/password=***/g' | sed 's/^/   /'
    fi
fi
echo ""

# Check if PostgreSQL is running locally
echo "4. PostgreSQL service status:"
if systemctl is-active --quiet postgresql; then
    echo "   PostgreSQL service is running"
elif systemctl is-active --quiet postgresql@*; then
    echo "   PostgreSQL service is running (version-specific)"
else
    echo "   PostgreSQL service status unknown (may be running in Docker)"
fi
echo ""

# Try to find Docker containers
echo "5. Checking Docker containers:"
if command -v docker &> /dev/null; then
    if docker ps 2>/dev/null | grep -q postgres; then
        echo "   PostgreSQL container found:"
        docker ps | grep postgres | sed 's/^/   /'
    else
        echo "   No PostgreSQL containers found"
    fi
else
    echo "   Docker not available"
fi
echo ""

# Check common PostgreSQL locations
echo "6. Common PostgreSQL connection info:"
echo "   To connect directly, try:"
echo "   - sudo -u postgres psql"
echo "   - psql -U postgres"
echo "   - psql -U postgres -d brain_capital"
echo ""
