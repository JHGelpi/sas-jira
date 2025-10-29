-- Migration: Add ship_cadence to database views
-- Date: 2025-10-28
-- Purpose: Update views to include ship_cadence column alongside normalized_sprint
--
-- Strategy: We keep both normalized_sprint and ship_cadence temporarily for backward compatibility
-- Once all systems are using ship_cadence, we can deprecate normalized_sprint

-- NOTE: This migration requires manual customization based on actual view definitions
-- The views need to be retrieved and updated appropriately

-- Step 1: Update view_jira_sprint_data
-- This view is the source of normalized_sprint calculation
-- We need to add ship_cadence column from tbl_jira_sprint_data

-- To retrieve current definition:
-- SELECT definition FROM pg_views WHERE viewname = 'view_jira_sprint_data';

-- Expected change:
-- Add: a.ship_cadence to the SELECT list
-- Keep: regexp_replace((a.sprint_name)::text, '.*(\d{4}\.\d{2}).*'::text, '\1'::text) AS normalized_sprint

-- Example (will need to be customized based on actual view):
/*
CREATE OR REPLACE VIEW view_jira_sprint_data AS
SELECT
    -- ... existing columns ...
    regexp_replace((a.sprint_name)::text, '.*(\d{4}\.\d{2}).*'::text, '\1'::text) AS normalized_sprint,
    a.ship_cadence,  -- NEW: Add ship_cadence from table
    -- ... rest of columns ...
FROM tbl_jira_sprint_data a
-- ... rest of view definition ...
*/

-- Step 2: Update view_jira_curr_record
-- This view references normalized_sprint from view_jira_sprint_data
-- We need to pass through ship_cadence as well

-- Expected change:
-- Add: a.ship_cadence to the SELECT list

-- Example:
/*
CREATE OR REPLACE VIEW view_jira_curr_record AS
SELECT
    -- ... existing columns ...
    a.normalized_sprint,  -- Keep for backward compatibility
    a.ship_cadence,       -- NEW: Add ship_cadence
    -- ... rest of columns ...
FROM view_jira_sprint_data a
-- ... rest of view definition ...
*/

-- Step 3: Update view_dedup_investment_flags
-- This view calculates normalized_sprint via regex on sprint_name
-- We need to add ship_cadence from the underlying data

-- Expected change:
-- Add: sprint.ship_cadence to the SELECT list (assuming sprint is the alias for sprint data)

-- Example:
/*
CREATE OR REPLACE VIEW view_dedup_investment_flags AS
SELECT
    -- ... existing columns ...
    regexp_replace((sprint.sprint_name)::text, '.*(\d{4}\.\d{2}).*'::text, '\1'::text) AS normalized_sprint,
    sprint.ship_cadence,  -- NEW: Add ship_cadence from join
    -- ... rest of columns ...
FROM view_jira_curr_record a
-- ... joins ...
-- ... rest of view definition ...
*/

-- ============================================================================
-- IMPORTANT: View Retrieval Commands
-- ============================================================================
-- Run these commands to get the current view definitions, then customize above:

-- Get view_jira_sprint_data definition:
SELECT definition FROM pg_views WHERE viewname = 'view_jira_sprint_data' AND schemaname = 'public';

-- Get view_jira_curr_record definition:
SELECT definition FROM pg_views WHERE viewname = 'view_jira_curr_record' AND schemaname = 'public';

-- Get view_dedup_investment_flags definition:
SELECT definition FROM pg_views WHERE viewname = 'view_dedup_investment_flags' AND schemaname = 'public';

-- ============================================================================
-- Testing Commands
-- ============================================================================
-- After updating views, verify ship_cadence column exists:

-- Test view_jira_sprint_data:
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'view_jira_sprint_data'
AND column_name IN ('normalized_sprint', 'ship_cadence');

-- Test view_jira_curr_record:
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'view_jira_curr_record'
AND column_name IN ('normalized_sprint', 'ship_cadence');

-- Test view_dedup_investment_flags:
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'view_dedup_investment_flags'
AND column_name IN ('normalized_sprint', 'ship_cadence');

-- Sample data verification:
SELECT normalized_sprint, ship_cadence, COUNT(*)
FROM view_dedup_investment_flags
GROUP BY normalized_sprint, ship_cadence
ORDER BY ship_cadence DESC
LIMIT 20;
