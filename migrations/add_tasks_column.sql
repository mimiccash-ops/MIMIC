-- Quick SQL migration: Add tasks column to tournaments table
-- Run this directly in PostgreSQL using psql:

ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS tasks JSON;

-- Verify the column was added:
-- SELECT column_name, data_type 
-- FROM information_schema.columns 
-- WHERE table_name = 'tournaments' AND column_name = 'tasks';
