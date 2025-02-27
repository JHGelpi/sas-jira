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
