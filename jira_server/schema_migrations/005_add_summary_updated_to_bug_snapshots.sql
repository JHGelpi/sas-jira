-- Migration: Add summary and updated columns to tbl_bug_snapshots
-- Date: 2025-01-21
-- Purpose: Enable interactive bug detail display in Bugs by Release chart

-- Check if summary column exists before adding (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'tbl_bug_snapshots'
        AND column_name = 'summary'
    ) THEN
        -- Add summary column
        ALTER TABLE tbl_bug_snapshots
        ADD COLUMN summary TEXT;

        -- Add comment for documentation
        COMMENT ON COLUMN tbl_bug_snapshots.summary
        IS 'Issue summary/title from Jira, used for displaying bug details in reports.';

        RAISE NOTICE 'summary column added successfully';
    ELSE
        RAISE NOTICE 'summary column already exists, skipping';
    END IF;
END $$;

-- Check if updated column exists before adding (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'tbl_bug_snapshots'
        AND column_name = 'updated'
    ) THEN
        -- Add updated column
        ALTER TABLE tbl_bug_snapshots
        ADD COLUMN updated TIMESTAMP;

        -- Add comment for documentation
        COMMENT ON COLUMN tbl_bug_snapshots.updated
        IS 'Last modified timestamp from Jira, used for displaying bug details in reports.';

        RAISE NOTICE 'updated column added successfully';
    ELSE
        RAISE NOTICE 'updated column already exists, skipping';
    END IF;
END $$;

-- Verify the changes
SELECT
    column_name,
    data_type,
    character_maximum_length,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'tbl_bug_snapshots'
AND column_name IN ('summary', 'updated')
ORDER BY column_name;
