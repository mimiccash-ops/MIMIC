-- Add payout and reward decision fields to task_participations
ALTER TABLE task_participations ADD COLUMN IF NOT EXISTS reward_type_given VARCHAR(50);
ALTER TABLE task_participations ADD COLUMN IF NOT EXISTS reward_description_given VARCHAR(500);
ALTER TABLE task_participations ADD COLUMN IF NOT EXISTS payout_method VARCHAR(50);
ALTER TABLE task_participations ADD COLUMN IF NOT EXISTS payout_details TEXT;
ALTER TABLE task_participations ADD COLUMN IF NOT EXISTS payout_contact VARCHAR(200);
ALTER TABLE task_participations ADD COLUMN IF NOT EXISTS payout_status VARCHAR(20) DEFAULT 'pending';
ALTER TABLE task_participations ADD COLUMN IF NOT EXISTS payout_reference VARCHAR(200);

UPDATE task_participations
SET payout_status = 'paid'
WHERE reward_given = TRUE AND payout_status IS NULL;

UPDATE task_participations
SET payout_status = 'pending'
WHERE payout_status IS NULL;
