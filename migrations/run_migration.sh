#!/bin/bash
# Migration script - tries multiple methods to add the tasks column

echo "=== Tournament Tasks Column Migration ==="
echo ""

SQL_COMMAND="ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS tasks JSON;"

# Method 1: Try using DATABASE_URL environment variable
if [ -n "$DATABASE_URL" ]; then
    echo "Attempting Method 1: Using DATABASE_URL from environment..."
    # Extract connection details from DATABASE_URL
    DB_URL=$(echo $DATABASE_URL | sed 's/postgres:\/\///' | sed 's/postgresql:\/\///')
    DB_USER=$(echo $DB_URL | cut -d: -f1)
    DB_PASS=$(echo $DB_URL | cut -d: -f2 | cut -d@ -f1)
    DB_HOST=$(echo $DB_URL | cut -d@ -f2 | cut -d: -f1)
    DB_PORT=$(echo $DB_URL | cut -d@ -f2 | cut -d: -f2 | cut -d/ -f1)
    DB_NAME=$(echo $DB_URL | cut -d/ -f2 | cut -d? -f1)
    
    export PGPASSWORD="$DB_PASS"
    if psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" -c "$SQL_COMMAND" 2>/dev/null; then
        echo "✅ Success! Column added via DATABASE_URL"
        exit 0
    fi
    unset PGPASSWORD
fi

# Method 2: Try as postgres superuser
echo "Attempting Method 2: Using postgres user..."
if sudo -u postgres psql -c "$SQL_COMMAND" 2>/dev/null; then
    echo "✅ Success! Column added via postgres user"
    exit 0
fi

# Method 3: Try common database names
echo "Attempting Method 3: Trying common database names..."
for DB_NAME in brain_capital mimic postgres; do
    echo "   Trying database: $DB_NAME"
    if sudo -u postgres psql -d "$DB_NAME" -c "$SQL_COMMAND" 2>/dev/null; then
        echo "✅ Success! Column added to database: $DB_NAME"
        exit 0
    fi
done

# Method 4: Try direct psql with different users
echo "Attempting Method 4: Trying different PostgreSQL users..."
for USER in postgres admin brain_capital; do
    echo "   Trying user: $USER"
    if psql -U "$USER" -d postgres -c "$SQL_COMMAND" 2>/dev/null; then
        echo "✅ Success! Column added via user: $USER"
        exit 0
    fi
done

echo ""
echo "❌ Could not connect to database automatically"
echo ""
echo "Please run the SQL manually:"
echo "  $SQL_COMMAND"
echo ""
echo "Try one of these:"
echo "  1. sudo -u postgres psql -d brain_capital"
echo "  2. psql -U postgres -d brain_capital"
echo "  3. Check your DATABASE_URL in config.ini or .env"
exit 1
