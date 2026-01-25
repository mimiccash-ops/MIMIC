#!/bin/bash
#
# Fix PostgreSQL user password
#

DB_USER="mimic_user"
DB_PASSWORD="bZNOkq0dXC2kD03HLjlHTlp9P"
DB_NAME="mimic_db"

echo "🔧 Fixing PostgreSQL user password..."

# Check if PostgreSQL is running
if ! systemctl is-active --quiet postgresql; then
    echo "❌ PostgreSQL is not running!"
    echo "Starting PostgreSQL..."
    sudo systemctl start postgresql
    sleep 2
fi

# Set password for user
echo "ℹ️  Setting password for user $DB_USER..."
sudo -u postgres psql << EOF
-- Create user if doesn't exist
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = '$DB_USER') THEN
        CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
    ELSE
        ALTER USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
    END IF;
END
\$\$;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
\q
EOF

if [[ $? -eq 0 ]]; then
    echo "✅ Password set successfully"
    
    # Test connection
    echo ""
    echo "🔍 Testing connection..."
    PGPASSWORD="$DB_PASSWORD" psql -h localhost -U "$DB_USER" -d "$DB_NAME" -c "SELECT version();" &> /dev/null
    
    if [[ $? -eq 0 ]]; then
        echo "✅ Connection successful!"
    else
        echo "⚠️  Connection test failed, but password was set"
        echo "Try connecting manually:"
        echo "  PGPASSWORD='$DB_PASSWORD' psql -h localhost -U $DB_USER -d $DB_NAME"
    fi
else
    echo "❌ Failed to set password"
    exit 1
fi
