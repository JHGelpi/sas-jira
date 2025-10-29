-- Original definition of view_jira_sprint_data
-- Retrieved: 2025-10-28 20:27:32

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
    regexp_replace((a.sprint_name)::text, '.*(\d{4}\.\d{2}).*'::text, '\1'::text) AS normalized_sprint
   FROM tbl_jira_sprint_data a
  ORDER BY a.export_date, a.issue_key DESC;;
