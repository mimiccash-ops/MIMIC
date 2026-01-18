# Tournament Tasks Feature - Migration Guide

## ✅ Files Updated

All necessary files have been updated to support tournament tasks/goals:

### 1. Database Model (`models.py`)
- ✅ Added `tasks` column (JSON) to Tournament model
- ✅ Updated `to_dict()` method to include tasks

### 2. API Endpoints (`app.py`)
- ✅ Updated `/api/admin/tournament/create` to handle tasks
- ✅ Added `/api/admin/tournaments` endpoint for listing
- ✅ Added `/api/admin/tournament/<id>` PUT endpoint for updates
- ✅ Fixed date format handling (datetime-local to ISO)

### 3. Admin Dashboard (`templates/dashboard_admin.html`)
- ✅ Added Tournaments section to navigation
- ✅ Added tournament creation modal with tasks support
- ✅ Added tournament list with tasks display
- ✅ Added JavaScript functions for tournament management
- ✅ Fixed input styling issues

### 4. Migration Scripts
- ✅ Updated `migrations/migrate.py` to include tasks column
- ✅ Created `migrations/add_tournament_tasks_column.py` standalone script

## 🚀 Running the Migration

### Option 1: Run Standalone Migration Script (Recommended)

On your Linux server, run:

```bash
cd /var/www/mimic
python3 migrations/add_tournament_tasks_column.py
```

This will:
- Check if the column exists
- Add it if missing
- Work with your database connection

### Option 2: Run Full Migration

```bash
cd /var/www/mimic
python3 migrations/migrate.py
```

This will:
- Add missing columns (including tasks)
- Create indexes
- Seed default data

### Option 3: Direct SQL (If migration scripts don't work)

Connect to your PostgreSQL database and run:

```sql
ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS tasks JSON;
```

## ✅ Verification

After running the migration, verify the column was added:

```sql
\d tournaments
```

You should see `tasks | json |` in the column list.

## 🎯 What's Now Available

After the migration:

1. **Create Tournaments with Tasks**
   - Go to Admin Dashboard → Tournaments section
   - Click "Create Tournament"
   - Fill in tournament details
   - Click "Add Task" to add tasks/goals
   - Each task can have:
     - Title
     - Description
     - Reward Type (Cash, XP, Bonus Entry)
     - Reward Amount
     - Required to win flag

2. **View Tournaments**
   - See all tournaments in the list
   - View task count badge on tournaments with tasks
   - Filter by status (active, upcoming, completed)

3. **Manage Tournaments**
   - Edit upcoming tournaments
   - Cancel active/upcoming tournaments
   - View tournament details

## 🔧 Troubleshooting

If you still see the error after running migration:

1. **Check if column exists:**
   ```sql
   SELECT column_name, data_type 
   FROM information_schema.columns 
   WHERE table_name = 'tournaments' AND column_name = 'tasks';
   ```

2. **Manually add if needed:**
   ```sql
   ALTER TABLE tournaments ADD COLUMN tasks JSON;
   ```

3. **Restart your application** after adding the column

## 📝 Notes

- The `tasks` column stores JSON array of task objects
- Each task contains: title, description, reward_type, reward_amount, required
- Tasks are optional - tournaments can be created without tasks
- The migration is safe to run multiple times (uses IF NOT EXISTS)
