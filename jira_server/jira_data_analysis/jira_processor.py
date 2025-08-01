import os
import csv
from datetime import datetime, timedelta
from io import StringIO
import psycopg2.extras

import db_utils
from jira_utils import parse_sprint_data, parse_label_data, parse_fix_version_data, parse_component_data, escaped_bug_flag, triage_parser, oper_parser, format_date

def build_jql(db_pool, jql_flag: str) -> str:
    """Builds the JQL query based on the last successful run log."""
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cursor:
            if jql_flag == 'daily':
                # Get the end time of the last successful daily run
                cursor.execute("""
                    SELECT MAX("endDTTM") FROM tbl_run_log WHERE "runType" = 'DAILY' AND "sprint" = 'daily';
                """)
                last_run_time = cursor.fetchone()[0]
                
                # If no previous run, fetch for the last 24 hours
                if last_run_time is None:
                    last_run_time_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M')
                else:
                    last_run_time_str = last_run_time.strftime('%Y-%m-%d %H:%M')
                
                jql = f"project in ({os.getenv('JIRA_PROJECTS')}) AND updated >= '{last_run_time_str}'"

            elif jql_flag == 'release':
                # Get the date of the latest release that has already occurred
                cursor.execute("""
                    SELECT MAX(release_date) FROM tbl_jira_releases WHERE release_date <= current_date;
                """)
                last_release_date = cursor.fetchone()[0]
                if last_release_date is None:
                    # Fallback if no releases are found
                    last_release_date = datetime.now().date()
                
                # Fetch data for the last 30 days leading up to the release
                start_date = last_release_date - timedelta(days=30)
                start_date_str = start_date.strftime('%Y-%m-%d')
                jql = f"project in ({os.getenv('JIRA_PROJECTS')}) AND statusCategory = Done AND updated >= '{start_date_str}' ORDER BY updated ASC"
            else:
                raise ValueError(f"Invalid jql_flag: {jql_flag}")
    finally:
        db_pool.putconn(conn)
        
    print(f"Constructed JQL for '{jql_flag}': {jql}")
    return jql

def fetch_all_issues(jira, jql_query: str) -> list:
    """Paginates through JIRA search results to fetch all issues for a given query."""
    all_issues = []
    start_at = 0
    max_results = 100 # A standard page size
    
    # Specify all fields you need in one go to avoid follow-up API calls
    fields = [
        "summary", "issuetype", "status", "assignee", "created", "updated",
        "issuelinks", "parent", "subtasks", "project", "labels", "fixVersions",
        "components",
        "customfield_10102", # Sprint Data
        "customfield_10301", # Epic Link
        "customfield_16301", # Parent Link
        "customfield_15600", # Pipeline Stage
        "customfield_14504", # Bug Origin
        "customfield_10002", # Story Points
    ]

    while True:
        try:
            issues = jira.search_issues(
                jql_query,
                startAt=start_at,
                maxResults=max_results,
                fields=fields,
                expand="changelog" # Expand changelog if you need status transition history
            )
            if not issues:
                break
            all_issues.extend(issues)
            start_at += len(issues)
        except Exception as e:
            print(f"Error fetching issues from Jira: {e}")
            break # Or implement retry logic
            
    print(f"Total issues fetched from Jira: {len(all_issues)}")
    return all_issues

def process_and_load_issues(db_pool, all_issues: list, run_flag: str):
    """
    Transforms Jira issue data and bulk-loads it into a PostgreSQL database.
    """
    print(f"Processing {len(all_issues)} issues...")
    
    # Pre-load lookup data from DB to avoid N+1 query problem
    sprint_managers = db_utils.load_sprint_managers(db_pool)
    operational_epics = db_utils.load_operational_epics(db_pool)

    # Use an in-memory string buffer for CSV data
    string_buffer = StringIO()
    writer = csv.writer(string_buffer)
    
    # Define headers that match the target table columns
    # Ensure this order matches your table and build_row output
    headers = [
        "epic_link", "parent_link", "oper_epic", "oper_flg", "triage_flg", "pipeline_stage",
        "bug_origin", "escaped_bug", "fix_version", "components", "issue_key", "summary",
        "issue_url", "issue_type", "sprint_name", "assignee", "status", "sprint_start_date",
        "sprint_end_date", "completed_date", "sprint_state", "labels", "sprint_owner", "export_date",
        "story_points", "run_flag", "jira_created_date", "jira_updated_date"
    ]
    writer.writerow(headers)

    for issue in all_issues:
        row = build_row(issue, sprint_managers, operational_epics, run_flag)
        writer.writerow(row)
        
    # Reset buffer position to the beginning to be read by copy_expert
    string_buffer.seek(0)
    
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cursor:
            # Use COPY for a highly efficient bulk insert
            # Assumes your table is named 'tbl_jira_sprint_data'
            sql_copy = f"COPY tbl_jira_sprint_data ({','.join(headers)}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE, DELIMITER ',')"
            cursor.copy_expert(sql=sql_copy, file=string_buffer)
            conn.commit()
            print(f"Successfully loaded {len(all_issues)} records into the database.")
    except Exception as e:
        conn.rollback()
        print(f"Database load failed: {e}")
    finally:
        db_pool.putconn(conn)


def build_row(issue, sprint_managers: dict, oper_epics: dict, run_flag: str) -> list:
    """Builds a single data row from a Jira issue object."""
    fields = issue.fields
    jira_server = os.getenv("JIRA_URL")
    
    assignee = fields.assignee.displayName if fields.assignee else 'Unassigned'
    status = fields.status.name if fields.status else 'No Status'
    issue_type = fields.issuetype.name if fields.issuetype else 'No Type'
    
    sprint_data_string = getattr(fields, 'customfield_10102', None)
    parsed_sprint = parse_sprint_data(sprint_data_string, sprint_managers)
    
    epic_link = getattr(fields, 'customfield_10301', None)
    
    # Parent can come from the parent field (standard) or a custom field
    parent_key = getattr(fields, 'parent', None)
    parent_link = parent_key.key if parent_key else getattr(fields, 'customfield_16301', None)
    
    labels_list = getattr(fields, 'labels', [])
    labels = parse_label_data(labels_list)
    
    pipeline_stage = str(getattr(fields, 'customfield_15600', ''))
    bug_origin = str(getattr(fields, 'customfield_14504', ''))
    
    story_points = getattr(fields, 'customfield_10002', 0)
    story_points = float(story_points) if story_points is not None else 0.0

    return [
        epic_link,
        parent_link,
        oper_epics.get(epic_link, ''), # Efficient lookup
        'Y' if oper_parser(labels_list) else 'N',
        'Y' if triage_parser(labels_list) else 'N',
        pipeline_stage,
        bug_origin,
        'Y' if escaped_bug_flag(bug_origin, pipeline_stage) else 'N',
        parse_fix_version_data(getattr(fields, 'fixVersions', [])),
        parse_component_data(getattr(fields, 'components', [])),
        issue.key,
        fields.summary,
        f'{jira_server.rstrip("/")}/browse/{issue.key}',
        issue_type,
        parsed_sprint['name'],
        assignee,
        status,
        parsed_sprint['start_date'],
        parsed_sprint['end_date'],
        parsed_sprint['complete_date'],
        parsed_sprint['state'],
        labels,
        parsed_sprint['owner'],
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        story_points,
        run_flag,
        format_date(fields.created),
        format_date(fields.updated)
    ]