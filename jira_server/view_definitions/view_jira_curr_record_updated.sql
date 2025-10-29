-- Updated definition of view_jira_curr_record
-- Date: 2025-10-28
-- Changes: Added ship_cadence column alongside normalized_sprint

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
