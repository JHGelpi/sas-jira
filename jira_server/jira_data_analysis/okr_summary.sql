-- This optimized query calculates investment metrics in a single pass over the data,
-- avoiding multiple scans and unions, making it much more efficient.

-- Step 1: Use a Common Table Expression (CTE) to filter the relevant data once.
-- A JOIN is generally more performant than a repeated EXISTS subquery.
WITH filtered_data AS (
    SELECT
        a.normalized_sprint,
        a.issue_key,
        a.sum_story_points,
        a.initiative_flag,
        a.bug_flag,
        a.iris
    FROM
        public.view_dedup_investment_flags AS a
    JOIN
        public.tbl_jira_releases AS r ON a.sprint_name LIKE '%' || r.fix_version || '%'
    WHERE
        r.release_date <= current_date
)
-- Step 2: Aggregate the filtered data, using a CASE statement to categorize investments.
SELECT
    -- This CASE statement categorizes each issue based on its flags.
    -- The order is important to ensure correct categorization (e.g., IRIS takes precedence).
    CASE
        WHEN iris = true THEN 'IRIS'
        WHEN bug_flag = 'Bug' THEN 'Bugs'
        WHEN initiative_flag = 'Y' THEN 'PM Initiative Investment'
        ELSE 'Operational'
    END AS investment_category,
    normalized_sprint,
    COUNT(issue_key) AS num_jiras,
    SUM(sum_story_points) AS story_points,
    -- This window function calculates the percentage of the sprint total efficiently
    -- without needing another join or subquery.
    ROUND(
        SUM(sum_story_points) * 100.0 /
        SUM(SUM(sum_story_points)) OVER (PARTITION BY normalized_sprint)
    ) AS pct_of_sprint_total
FROM
    filtered_data
-- Group by the generated category and the sprint
GROUP BY
    investment_category,
    normalized_sprint
-- Order the final result for clear presentation
ORDER BY
    normalized_sprint,
    investment_category;