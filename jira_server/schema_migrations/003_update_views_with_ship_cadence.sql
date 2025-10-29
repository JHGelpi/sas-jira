-- Migration: Update all views to include ship_cadence column
-- Date: 2025-10-28
-- Purpose: Add ship_cadence to views alongside normalized_sprint for backward compatibility
--
-- IMPORTANT: Run this AFTER 001_add_ship_cadence_column.sql has been executed
-- and AFTER backfill has been completed

-- ============================================================================
-- View 1: view_jira_sprint_data
-- ============================================================================
-- This is the base view that sources data from tbl_jira_sprint_data
-- Change: Added ship_cadence column from table (line 51)

CREATE OR REPLACE VIEW view_jira_sprint_data AS
 SELECT
        CASE
            WHEN ((a.epic_link)::text <> ''::text) THEN a.epic_link
            ELSE a.parent_link
        END AS issue_parent,
    a.epic_link,
    a.parent_link,
    a.operational_epic_team,
    a.operational_flag,
    a.triage_origin_flag,
    a.pipeline_stage,
    a.bug_origin,
    a.escaped_bug_flag,
    a.fix_version,
    a.components,
    a.issue_key,
    a.issue_summary,
    a.issue_url,
    a.issue_type,
    a.issue_state,
    a.issue_assignee,
        CASE
            WHEN (TRIM(BOTH FROM a.status) = 'Accepted and Close(Q)'::text) THEN 'Closed'::character varying
            WHEN (TRIM(BOTH FROM a.status) = 'Developing(W)'::text) THEN 'In Progress'::character varying
            WHEN (TRIM(BOTH FROM a.status) = 'In Dev'::text) THEN 'In Progress'::character varying
            WHEN (TRIM(BOTH FROM a.status) = 'Dev-ready(Q)'::text) THEN 'Dev Ready'::character varying
            WHEN (TRIM(BOTH FROM a.status) = 'Ready for Dev'::text) THEN 'Dev Ready'::character varying
            WHEN (TRIM(BOTH FROM a.status) = 'In Test'::text) THEN 'Testing'::character varying
            WHEN (TRIM(BOTH FROM a.status) = 'Testing(W)'::text) THEN 'Testing'::character varying
            WHEN (TRIM(BOTH FROM a.status) = 'Test-ready(Q)'::text) THEN 'Ready for Test'::character varying
            WHEN (TRIM(BOTH FROM a.status) = 'Review-ready(Q)'::text) THEN 'Review-ready'::character varying
            ELSE a.status
        END AS issue_status,
    a.story_points,
    a.start_date,
    a.end_date,
    a.sprint_name,
    a.labels,
    a.sprint_owner,
    a.update_date,
    a.id,
    a.completed_date,
    a.run_flag,
    a.jira_created_date,
    a.jira_updated_date,
    a.export_date,
    regexp_replace((a.sprint_name)::text, '.*(\d{4}\.\d{2}).*'::text, '\1'::text) AS normalized_sprint,
    a.ship_cadence  -- NEW: Add ship_cadence from table
   FROM tbl_jira_sprint_data a
  ORDER BY a.export_date, a.issue_key DESC;

-- Verify view_jira_sprint_data update
SELECT 'view_jira_sprint_data' AS view_name,
       COUNT(*) AS column_count
FROM information_schema.columns
WHERE table_name = 'view_jira_sprint_data'
AND column_name IN ('normalized_sprint', 'ship_cadence');
-- Expected: 2 rows (both columns should exist)

-- ============================================================================
-- View 2: view_jira_curr_record
-- ============================================================================
-- This view references view_jira_sprint_data
-- Change: Added ship_cadence column from view_jira_sprint_data (line 20)

CREATE OR REPLACE VIEW view_jira_curr_record AS
 SELECT a.issue_key,
    a.issue_url,
    a.issue_type,
    a.issue_status,
    a.story_points,
    a.sprint_name,
    a.start_date,
    a.end_date,
    a.completed_date,
    a.run_flag,
    a.jira_created_date,
    a.jira_updated_date,
    a.issue_parent,
    a.epic_link,
    b.initiative_key,
    b.iris,
    a.escaped_bug_flag,
    a.update_date,
    a.normalized_sprint,
    a.ship_cadence,  -- NEW: Add ship_cadence from view_jira_sprint_data
    a.export_date
   FROM ((view_jira_sprint_data a
     LEFT JOIN ( SELECT c_1.issue_key AS initiative_key,
            b_1.issue_key,
            c_1."IRIS" AS iris,
            max(b_1.effective_dttm) AS max
           FROM (tbl_initiative_children b_1
             JOIN tbl_initiative_issue_keys c_1 ON (((c_1.issue_key)::text = (b_1.initiative_issue_key)::text)))
          GROUP BY b_1.issue_key, c_1.issue_key, c_1."IRIS") b ON (((b.issue_key)::text = (a.issue_key)::text)))
     JOIN ( SELECT c_1.issue_key,
            max(c_1.update_date) AS update_date,
            max(c_1.export_date) AS export_date
           FROM view_jira_sprint_data c_1
          GROUP BY c_1.issue_key) c ON ((((c.issue_key)::text = (a.issue_key)::text) AND (c.export_date = a.export_date))))
  ORDER BY a.issue_key DESC;

-- Verify view_jira_curr_record update
SELECT 'view_jira_curr_record' AS view_name,
       COUNT(*) AS column_count
FROM information_schema.columns
WHERE table_name = 'view_jira_curr_record'
AND column_name IN ('normalized_sprint', 'ship_cadence');
-- Expected: 2 rows (both columns should exist)

-- ============================================================================
-- View 3: view_dedup_investment_flags
-- ============================================================================
-- This view is used by okr_summary.sql for investment trends
-- Changes:
--   1. Added ship_cadence to main SELECT (line 7)
--   2. Added ship_cadence to sprint subquery SELECT (line 32)
--   3. Added ship_cadence to sprint subquery GROUP BY (line 35)
--   4. Added ship_cadence to main GROUP BY (line 39)

CREATE OR REPLACE VIEW view_dedup_investment_flags AS
 SELECT a.issue_key,
    iris.iris,
    bug.issue_type AS bug_flag,
    initiative.initiative_flag,
    sprint.sprint_name,
    regexp_replace((sprint.sprint_name)::text, '.*(\d{4}\.\d{2}).*'::text, '\1'::text) AS normalized_sprint,
    sprint.ship_cadence,  -- NEW: Add ship_cadence from sprint subquery
    count(a.issue_key) AS num_jiras,
    (sum(a.story_points) / (count(a.issue_key))::double precision) AS sum_story_points
   FROM ((((view_jira_curr_record a
     LEFT JOIN ( SELECT iris_1.issue_key,
            iris_1.iris
           FROM view_jira_curr_record iris_1
          WHERE (iris_1.iris = true)
          GROUP BY iris_1.issue_key, iris_1.iris) iris ON (((iris.issue_key)::text = (a.issue_key)::text)))
     LEFT JOIN ( SELECT bug_1.issue_key,
            bug_1.issue_type
           FROM view_jira_curr_record bug_1
          WHERE ((bug_1.issue_type)::text = 'Bug'::text)
          GROUP BY bug_1.issue_key, bug_1.issue_type) bug ON (((bug.issue_key)::text = (a.issue_key)::text)))
     LEFT JOIN ( SELECT initiatives.issue_key,
            initiatives.issue_type,
            'Y'::text AS initiative_flag
           FROM view_jira_curr_record initiatives
          WHERE (((initiatives.iris = false) OR (initiatives.iris IS NULL)) AND (initiatives.initiative_key IS NOT NULL) AND ((initiatives.issue_type)::text = ANY (ARRAY[('Story'::character varying)::text, ('Task'::character varying)::text, ('Security Issue'::character varying)::text, ('Bug'::character varying)::text, ('Research'::character varying)::text])))
          GROUP BY initiatives.issue_key, initiatives.issue_type) initiative ON (((initiative.issue_key)::text = (a.issue_key)::text)))
     LEFT JOIN ( SELECT sprint_1.issue_key,
            sprint_1.issue_type,
            sprint_1.sprint_name,
            sprint_1.ship_cadence  -- NEW: Add ship_cadence to sprint subquery
           FROM view_jira_curr_record sprint_1
          WHERE ((sprint_1.issue_status)::text = ANY (ARRAY[('Closed'::character varying)::text, ('Done'::character varying)::text]))
          GROUP BY sprint_1.issue_key, sprint_1.issue_type, sprint_1.sprint_name, sprint_1.ship_cadence
          ORDER BY sprint_1.issue_key DESC) sprint ON (((sprint.issue_key)::text = (a.issue_key)::text)))
  WHERE (((a.sprint_name)::text ~~ ANY (ARRAY['%2025.%'::text])) AND ((a.issue_status)::text = ANY (ARRAY[('Closed'::character varying)::text, ('Done'::character varying)::text])) AND ((a.issue_type)::text = ANY (ARRAY[('Story'::character varying)::text, ('Task'::character varying)::text, ('Security Issue'::character varying)::text, ('Bug'::character varying)::text, ('Research'::character varying)::text])))
  GROUP BY a.issue_key, iris.iris, bug.issue_type, initiative.initiative_flag, sprint.sprint_name, sprint.ship_cadence
  ORDER BY (count(a.issue_key)) DESC;

-- Verify view_dedup_investment_flags update
SELECT 'view_dedup_investment_flags' AS view_name,
       COUNT(*) AS column_count
FROM information_schema.columns
WHERE table_name = 'view_dedup_investment_flags'
AND column_name IN ('normalized_sprint', 'ship_cadence');
-- Expected: 2 rows (both columns should exist)

-- ============================================================================
-- Final Verification
-- ============================================================================

-- Check all three views have both columns
SELECT
    table_name,
    COUNT(CASE WHEN column_name = 'normalized_sprint' THEN 1 END) AS has_normalized_sprint,
    COUNT(CASE WHEN column_name = 'ship_cadence' THEN 1 END) AS has_ship_cadence
FROM information_schema.columns
WHERE table_name IN ('view_jira_sprint_data', 'view_jira_curr_record', 'view_dedup_investment_flags')
AND column_name IN ('normalized_sprint', 'ship_cadence')
GROUP BY table_name
ORDER BY table_name;
-- Expected: Each view should have both columns (1, 1)

-- Sample data comparison
SELECT
    normalized_sprint,
    ship_cadence,
    COUNT(*) AS record_count
FROM view_dedup_investment_flags
GROUP BY normalized_sprint, ship_cadence
ORDER BY ship_cadence DESC NULLS LAST
LIMIT 20;
-- This shows how normalized_sprint and ship_cadence values compare

RAISE NOTICE 'View migration completed successfully';
RAISE NOTICE 'All views now have both normalized_sprint and ship_cadence columns';
RAISE NOTICE 'Next step: Test okr_summary.sql and investment_trends.py';
