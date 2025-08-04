'''
--Investment in our Initiatives
--Requries the run of initiative_children.py
select 
	--a.initiative_issue_key,
	count(a.issue_key) num_issues,
	sum(a.story_points) points
	from public.tbl_initiative_children a 
	join public.tbl_initiative_issue_keys b on b.issue_key = a.initiative_issue_key
	where a.issue_type = 'Story'
	and b."IRIS" = 'false'
    and a.effective_dttm >= '2025-01-01'
    and a.effective_dttm < '2025-04-01'
	--group by a.initiative_issue_key
	--order by a.initiative_issue_key
	;
'''