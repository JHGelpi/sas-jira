-- Original definition of view_dedup_investment_flags
-- Retrieved: 2025-10-28 20:27:32

CREATE OR REPLACE VIEW view_dedup_investment_flags AS
 SELECT a.issue_key,
    iris.iris,
    bug.issue_type AS bug_flag,
    initiative.initiative_flag,
    sprint.sprint_name,
    regexp_replace((sprint.sprint_name)::text, '.*(\d{4}\.\d{2}).*'::text, '\1'::text) AS normalized_sprint,
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
            sprint_1.sprint_name
           FROM view_jira_curr_record sprint_1
          WHERE ((sprint_1.issue_status)::text = ANY (ARRAY[('Closed'::character varying)::text, ('Done'::character varying)::text]))
          GROUP BY sprint_1.issue_key, sprint_1.issue_type, sprint_1.sprint_name
          ORDER BY sprint_1.issue_key DESC) sprint ON (((sprint.issue_key)::text = (a.issue_key)::text)))
  WHERE (((a.sprint_name)::text ~~ ANY (ARRAY['%2025.%'::text])) AND ((a.issue_status)::text = ANY (ARRAY[('Closed'::character varying)::text, ('Done'::character varying)::text])) AND ((a.issue_type)::text = ANY (ARRAY[('Story'::character varying)::text, ('Task'::character varying)::text, ('Security Issue'::character varying)::text, ('Bug'::character varying)::text, ('Research'::character varying)::text])))
  GROUP BY a.issue_key, iris.iris, bug.issue_type, initiative.initiative_flag, sprint.sprint_name
  ORDER BY (count(a.issue_key)) DESC;;
