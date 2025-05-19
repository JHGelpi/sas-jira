SELECT 
    a.investment_category,
    a.normalized_sprint,
    a.num_jiras,
    a.story_points,
    ROUND(a.story_points * 100.0 / SUM(a.story_points) OVER (PARTITION BY a.normalized_sprint)) AS pct_of_sprint_total
FROM (
    SELECT 'PM Initiative Investment' as investment_category,
        a.normalized_sprint,
        count(a.issue_key) as num_jiras,
        sum(a.sum_story_points) as story_points 
    FROM public.view_dedup_investment_flags a
    WHERE a.sprint_name LIKE ANY (ARRAY['%2025.01%', '%2025.02%', '%2025.03%', '%2025.04%', '%2025.05%'])
        AND a.iris is null
        AND a.initiative_flag = 'Y'
    GROUP BY a.normalized_sprint
    UNION
    SELECT 'Operational' as investment_category,
        a.normalized_sprint,
        count(a.issue_key) as num_jiras,
        sum(a.sum_story_points) as story_points 
    FROM public.view_dedup_investment_flags a
    WHERE a.sprint_name LIKE ANY (ARRAY['%2025.01%', '%2025.02%', '%2025.03%', '%2025.04%', '%2025.05%'])
        AND a.iris is null
        AND a.initiative_flag is null
        AND a.bug_flag is null
    GROUP BY a.normalized_sprint
    UNION
    SELECT 'Bugs' as investment_category,
        a.normalized_sprint,
        count(a.issue_key) as num_jiras,
        sum(a.sum_story_points) as story_points 
    FROM public.view_dedup_investment_flags a
    WHERE a.sprint_name LIKE ANY (ARRAY['%2025.01%', '%2025.02%', '%2025.03%', '%2025.04%', '%2025.05%'])
        AND a.bug_flag = 'Bug'
        AND a.iris is null
    GROUP BY a.normalized_sprint
    UNION
    SELECT 'IRIS' as investment_category,
        a.normalized_sprint,
        count(a.issue_key) as num_jiras,
        sum(a.sum_story_points) as story_points 
    FROM public.view_dedup_investment_flags a
    WHERE a.sprint_name LIKE ANY (ARRAY['%2025.01%', '%2025.02%', '%2025.03%', '%2025.04%', '%2025.05%'])
        AND a.iris = true
    GROUP BY a.normalized_sprint
) a
ORDER BY a.normalized_sprint, a.investment_category;