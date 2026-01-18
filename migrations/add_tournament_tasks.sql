-- Quick SQL fix: Add tasks column to tournaments table
-- Run this directly in PostgreSQL: psql -U your_user -d your_database -f migrations/add_tournament_tasks.sql
-- Or copy and paste this SQL into your PostgreSQL client:

ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS tasks JSON;
