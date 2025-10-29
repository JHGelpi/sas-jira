-- Migration: Add ship_cadence column to tbl_jira_sprint_data
-- Date: 2025-10-28
-- Purpose: Migrate from sprint_name-based normalized_sprint to fix_version-based ship_cadence

-- Check if column exists before adding (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'tbl_jira_sprint_data'
        AND column_name = 'ship_cadence'
    ) THEN
        -- Add new column for materialized ship cadence
        ALTER TABLE tbl_jira_sprint_data
        ADD COLUMN ship_cadence VARCHAR(7);

        -- Add comment for documentation
        COMMENT ON COLUMN tbl_jira_sprint_data.ship_cadence
        IS 'Latest valid fix version in YYYY.MM format, derived from fix_version field. Represents the ship/release cadence.';

        RAISE NOTICE 'ship_cadence column added successfully';
    ELSE
        RAISE NOTICE 'ship_cadence column already exists, skipping';
    END IF;
END $$;

-- Check if index exists before creating (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE tablename = 'tbl_jira_sprint_data'
        AND indexname = 'idx_jira_sprint_data_ship_cadence'
    ) THEN
        -- Add index for performance (frequently used in WHERE/GROUP BY)
        CREATE INDEX idx_jira_sprint_data_ship_cadence
        ON tbl_jira_sprint_data(ship_cadence);

        RAISE NOTICE 'Index idx_jira_sprint_data_ship_cadence created successfully';
    ELSE
        RAISE NOTICE 'Index idx_jira_sprint_data_ship_cadence already exists, skipping';
    END IF;
END $$;

-- Verify the changes
SELECT
    column_name,
    data_type,
    character_maximum_length,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'tbl_jira_sprint_data'
AND column_name = 'ship_cadence';

-- Check index
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'tbl_jira_sprint_data'
AND indexname = 'idx_jira_sprint_data_ship_cadence';
