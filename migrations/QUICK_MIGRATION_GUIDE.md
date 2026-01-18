# Quick Migration Guide - Add Tasks Column

The migration script needs Flask dependencies which might not be available in your environment.
Here are **3 easy ways** to add the column:

## Option 1: Direct SQL (FASTEST - Recommended) ⚡

If you have direct access to PostgreSQL, just run:

```bash
psql -U your_username -d your_database_name -c "ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS tasks JSON;"
```

Or if using docker-compose:
```bash
docker-compose exec db psql -U brain_capital -d brain_capital -c "ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS tasks JSON;"
```

## Option 2: SQL File

```bash
# Copy the SQL from migrations/add_tasks_column.sql
# Then run:
psql -U your_username -d your_database_name -f migrations/add_tasks_column.sql
```

## Option 3: Simple Python Script (No Flask)

The simple script uses only psycopg2:

```bash
# Make sure psycopg2 is installed
pip3 install psycopg2-binary

# Set DATABASE_URL if not already set
export DATABASE_URL=postgresql://user:password@host:5432/database

# Run the migration
python3 migrations/add_tasks_column_simple.py
```

## What This Does

- Adds `tasks` column (JSON type) to `tournaments` table
- Safe to run multiple times (uses IF NOT EXISTS)
- No data loss - existing tournaments will have NULL tasks

## Verify It Worked

After running the migration, check:

```sql
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'tournaments' AND column_name = 'tasks';
```

You should see: `tasks | json`

## After Migration

1. Restart your application
2. The database errors will stop
3. You can now create tournaments with tasks from admin dashboard
