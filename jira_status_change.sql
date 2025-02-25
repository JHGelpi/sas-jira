/*view_jira_status_changes*/
CREATE VIEW jira_status_changes AS
SELECT 
    a.issue_key,
    a.issue_type,
    MAX(a.update_date) AS previous_update_date,
    b.update_date AS current_update_date,
    a.issue_status AS previous_status,
    b.issue_status AS current_status,
    a.id
FROM 
    view_jira_sprint_data a
JOIN 
    view_jira_sprint_data b 
    ON a.issue_key = b.issue_key 
    AND a.update_date < b.update_date
WHERE 
    a.issue_status <> b.issue_status
    AND a.run_flag = 'daily'
    AND b.run_flag = 'daily'
    --AND a.issue_key = 'COMPDIV-14'
GROUP BY
    a.issue_key,
    a.issue_type,
    b.update_date,
    b.issue_status,
    a.issue_status,
    a.id
HAVING 
    MAX(a.update_date) = (
        SELECT MAX(a1.update_date)
        FROM view_jira_sprint_data a1
        WHERE a1.issue_key = a.issue_key
        AND a1.update_date < b.update_date
        AND a1.run_flag = 'daily'
    )
ORDER BY a.issue_key;

/*view_jira_sprint_data*/
 SELECT
        CASE
            WHEN a.epic_link::text <> ''::text THEN a.epic_link
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
            WHEN TRIM(BOTH FROM a.issue_status) = 'Accepted and Close(Q)'::text THEN 'Closed'::character varying
            WHEN TRIM(BOTH FROM a.issue_status) = 'Developing(W)'::text THEN 'In Progress'::character varying
            WHEN TRIM(BOTH FROM a.issue_status) = 'In Dev'::text THEN 'In Progress'::character varying
            WHEN TRIM(BOTH FROM a.issue_status) = 'Dev-ready(Q)'::text THEN 'Dev Ready'::character varying
            WHEN TRIM(BOTH FROM a.issue_status) = 'Ready for Dev'::text THEN 'Dev Ready'::character varying
            WHEN TRIM(BOTH FROM a.issue_status) = 'In Test'::text THEN 'Testing'::character varying
            WHEN TRIM(BOTH FROM a.issue_status) = 'Testing(W)'::text THEN 'Testing'::character varying
            WHEN TRIM(BOTH FROM a.issue_status) = 'Test-ready(Q)'::text THEN 'Ready for Test'::character varying
            WHEN TRIM(BOTH FROM a.issue_status) = 'Review-ready(Q)'::text THEN 'Review-ready'::character varying
            ELSE a.issue_status
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
    a.run_flag
   FROM tbl_jira_sprint_data a
  ORDER BY a.end_date DESC, a.issue_key DESC;