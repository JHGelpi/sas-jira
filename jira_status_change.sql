SELECT 
    a.id,
    a.issue_key,
    a.issue_type,
    a.update_date AS update_date,
    a.jira_created_date,
    a.issue_status AS previous_status,
    b.issue_status AS current_status,
    CASE
        WHEN LOWER(REPLACE(TRIM(b.issue_status), ' ', '')) = LOWER(REPLACE(TRIM(a.issue_status), ' ', '')) THEN 'CURR'
        ELSE 'HIST' 
    END AS current_flg,
    CASE
        WHEN b.issue_status = 'In Progress' THEN EXTRACT(DAY FROM AGE(b.update_date, a.jira_created_date))
        ELSE NULL
    END AS days_to_in_progress
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
GROUP BY
    a.id,
    a.issue_key,
    a.issue_type,
    a.jira_created_date,
    a.update_date,
    b.update_date,
    b.issue_status,
    a.issue_status
HAVING 
    MAX(a.update_date) = (
        SELECT MAX(a1.update_date)
        FROM view_jira_sprint_data a1
        WHERE a1.issue_key = a.issue_key
        AND a1.update_date < b.update_date
        AND a1.run_flag = 'daily'
    )
UNION
SELECT 
    a.id,
    a.issue_key,
    a.issue_type,
    a.update_date AS update_date,
    a.jira_created_date,
    a.issue_status AS previous_status,
    a.issue_status AS current_status,
    NULL AS current_flg,
    CASE
        WHEN a.issue_status = 'In Progress' THEN EXTRACT(DAY FROM AGE(a.update_date, a.jira_created_date))
        ELSE NULL
    END AS days_to_in_progress
FROM 
    view_jira_sprint_data a
WHERE 
    a.run_flag = 'daily'
    AND (SELECT MAX(b.update_date) FROM view_jira_sprint_data b
         WHERE b.issue_key = a.issue_key) = a.update_date
ORDER BY issue_key, update_date DESC;

--Investment in our Initiatives
-- Create a view combining the two queries
CREATE OR REPLACE VIEW view_initiative_and_points_summary AS
WITH initiative_data AS (
    -- Requires the run of initiative_children.py
    SELECT 
        COUNT(a.issue_key) AS num_initiative_issues,
        SUM(a.story_points) AS initiative_points
    FROM public.tbl_initiative_children a 
    JOIN public.tbl_initiative_issue_keys b ON b.issue_key = a.initiative_issue_key
    WHERE a.issue_type = 'Story'
      AND b."IRIS" = 'false'
      AND a.effective_dttm >= '2025-01-01'
      AND a.effective_dttm < '2025-04-01'
),
total_points_data AS (
    -- Total points accepted and closed in 2025
    SELECT 
        SUM(a.story_points) AS total_points
    FROM public.tbl_jira_sprint_data a
    JOIN (
        SELECT a.issue_key,
               MAX(a.id) AS max_id
        FROM public.tbl_jira_sprint_data a
        WHERE a.issue_status IN ('Closed', 'Accepted and Close(Q)')
        GROUP BY a.issue_key
    ) b ON a.id = b.max_id
    WHERE a.completed_date >= '2025-01-01'
      AND a.completed_date < '2025-04-01'
      AND a.issue_status IN ('Closed', 'Accepted and Close(Q)')
),
bug_points_data AS (
    -- Total bug story points in 2025, summing the average points per issue
    SELECT 
        SUM(issue_avg_points) AS bug_points
    FROM (
        SELECT 
            a.issue_key,
            SUM(a.story_points) / COUNT(a.issue_key) AS issue_avg_points
        FROM public.tbl_jira_sprint_data a
        WHERE a.issue_type = 'Bug'
          AND a.completed_date >= '2025-01-01'
          AND a.completed_date < '2025-04-01'
          AND a.issue_status IN ('Closed', 'Accepted and Close(Q)')
        GROUP BY a.issue_key
    ) subquery
)
SELECT 
	t.total_points,
    i.num_initiative_issues,
    i.initiative_points,
    b.bug_points,
    t.total_points - (i.initiative_points + b.bug_points) AS operational_points
FROM initiative_data i
CROSS JOIN total_points_data t
CROSS JOIN bug_points_data b;

-- Escaped bugs time to resolution
select a.issue_key,
    a.jira_created_date,
    a.jira_updated_date,
    a.sprint_name,
    EXTRACT(DAY FROM (DATE_TRUNC('day', a.jira_updated_date) - DATE_TRUNC('day', a.jira_created_date))) AS resolution_time_days
from public.tbl_jira_sprint_data a
where a.issue_status in('Closed', 'Accepted and Close(Q)')
and a.issue_type = 'Bug'
and a.escaped_bug_flag = 'Y'
and a.sprint_name like '%2025.%'
and a.jira_created_date is not null
;



--This SQL will be used to identify the mix of story points
--based on investment (tbl_initiative_children to show how many
--story points we invested in a given initiative), bugs, IRIS, and
--operational/other.  Those four categories will total 100% of the story
--points for a given sprint
SELECT a.issue_key, a.issue_url, a.issue_type, a.issue_status, a.story_points, a.sprint_name, 
	a.start_date, a.end_date, a.completed_date, a.run_flag, a.jira_created_date, a.jira_updated_date, 
	a.issue_parent, a.epic_link, b.initiative_key, b.iris, a.escaped_bug_flag
	FROM public.view_jira_sprint_data a
	LEFT OUTER JOIN (SELECT c.issue_key as initiative_key,
	b.issue_key,
	c."IRIS" as iris,
	max(b.effective_dttm)
	FROM public.tbl_initiative_children b
	JOIN public.tbl_initiative_issue_keys c ON c.issue_key = b.initiative_issue_key
	group by b.issue_key, c.issue_key, c."IRIS") b on b.issue_key = a.issue_key
	;