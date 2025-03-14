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
select 
	--a.initiative_issue_key,
	count(a.issue_key) num_issues,
	sum(a.story_points) points
	from public.tbl_initiative_children a 
	join public.tbl_initiative_issue_keys b on b.issue_key = a.initiative_issue_key
	where a.issue_type = 'Story'
	and b."IRIS" = 'false'
	--group by a.initiative_issue_key
	--order by a.initiative_issue_key
	;

--Total points accepted and closed in 2025
select --a.issue_status,
	sum(a.story_points) total_points
	from public.tbl_jira_sprint_data a
	join (select a.issue_key,
		max(a.id) max_id
		from public.tbl_jira_sprint_data a
		where a.issue_status in('Closed', 'Accepted and Close(Q)')
		group by a.issue_key
	order by a.issue_key) b on a.id = b.max_id
	where a.completed_date >= '2025-01-01'
	and a.issue_status in('Closed', 'Accepted and Close(Q)')
	--group by a.issue_status
	;