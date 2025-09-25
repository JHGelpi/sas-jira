import os
import csv
from datetime import datetime, timedelta
from io import StringIO

from . import db_utils
from .jira_utils import (
    parse_sprint_data, parse_label_data, parse_fix_version_data, 
    parse_component_data, escaped_bug_flag, triage_parser, oper_parser, 
    format_date, get_custom_field_id
)
import logging

logger = logging.getLogger(__name__)

def build_daily_jql(db_pool) -> str:
    """Builds the JQL query for the standard daily delta run."""
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT MAX("endDTTM") FROM tbl_run_log WHERE ("runType" = 'DAILY' OR "runType" = 'daily');
            """)
            last_run_time = cursor.fetchone()[0]
            
            if last_run_time is None:
                last_run_time_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M')
            else:
                last_run_time_str = last_run_time.strftime('%Y-%m-%d %H:%M')
            
            jql = f"project in ({os.getenv('JIRA_PROJECTS')}) AND updated >= '{last_run_time_str}'"
    finally:
        db_pool.putconn(conn)
        
    logger.info(f"Constructed JQL for 'daily': {jql}")
    return jql

def get_sprint_names_from_db(db_pool):
    """Fetches all sprint names from the sprint dates table."""
    conn = db_pool.getconn()
    sprint_names = []
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT sprint_name FROM public.tbl_sprint_dates")
            sprint_names = [row[0] for row in cursor.fetchall()]
    finally:
        db_pool.putconn(conn)
    return sprint_names

def get_last_release_run_time(db_pool):
    """Gets the end time of the last successful release run."""
    conn = db_pool.getconn()
    last_run_time = None
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT MAX("endDTTM") FROM tbl_run_log WHERE "runType" = 'RELEASE';
            """)
            last_run_time = cursor.fetchone()[0]
    finally:
        db_pool.putconn(conn)
    
    if last_run_time is None:
        return (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d %H:%M')
    else:
        return last_run_time.strftime('%Y-%m-%d %H:%M')

def process_release_data(jira, db_pool):
    """Orchestrates the new release data processing logic."""
    logger.info("Starting new, targeted release data processing logic...")
    
    sprint_names_to_match = get_sprint_names_from_db(db_pool)
    if not sprint_names_to_match:
        logger.warning("No sprint names found in tbl_sprint_dates. Aborting release run.")
        return

    last_run_time_str = get_last_release_run_time(db_pool)
    jql_query = f"project in ({os.getenv('JIRA_PROJECTS')}) AND updated >= '{last_run_time_str}'"
    logger.info(f"Fetching all potentially relevant issues with JQL: {jql_query}")

    fields_to_fetch = get_required_field_list(jira)
    all_fetched_issues = fetch_all_issues(jira, jql_query, fields_to_fetch)

    if not all_fetched_issues:
        logger.info("No recently updated issues found in Jira. Aborting release run.")
        return

    logger.info("Filtering issues based on sprint name criteria...")
    issues_to_load = []
    sprint_field_id = get_custom_field_id(jira, "Sprint") 

    # --- NEW: Add a counter for diagnostic logging ---
    debug_counter = 0
    for issue in all_fetched_issues:
        sprint_data = getattr(issue.fields, sprint_field_id, None)
        
        # --- NEW: Diagnostic Logging ---
        # This will log the raw sprint data for the first 5 issues processed.
        if debug_counter < 5:
            logger.info(f"DIAGNOSTIC [{issue.key}]: Raw sprint data from Jira API: {sprint_data}")
            debug_counter += 1

        parsed_sprint = parse_sprint_data(sprint_data, {})
        issue_sprint_name = parsed_sprint.get('name')

        if issue_sprint_name and any(target in issue_sprint_name for target in sprint_names_to_match):
            issues_to_load.append(issue)

    logger.info(f"Found {len(issues_to_load)} issues matching the release criteria to load.")
    if issues_to_load:
        process_and_load_issues(db_pool, issues_to_load, 'release', jira)


def get_required_field_list(jira):
    """Helper function to build the list of all fields needed for processing."""
    base_fields = ["summary", "issuetype", "status", "assignee", "created", "updated",
                   "issuelinks", "parent", "subtasks", "project", "labels", "fixVersions", "components"]
    
    custom_field_ids = [
        get_custom_field_id(jira, "Sprint"),
        get_custom_field_id(jira, "Epic Link"),
        get_custom_field_id(jira, "Parent Link"),
        get_custom_field_id(jira, "Pipeline Discovery Stage"),
        get_custom_field_id(jira, "Origin"),
        get_custom_field_id(jira, "Story Points"),
    ]
    
    return base_fields + [id for id in custom_field_ids if id]


def fetch_all_issues(jira, jql_query: str, fields: list) -> list:
    """Paginates through JIRA search results to fetch all issues for a given query."""
    all_issues = []
    logger.info(f"Fetching all issues with JQL: {jql_query}")
    try:
        all_issues = jira.search_issues(jql_query, fields=fields, maxResults=False, expand="changelog")
        logger.info(f"Total issues fetched from Jira: {len(all_issues)}")
    except Exception as e:
        logger.error(f"Error fetching issues from Jira: {e}")
    return all_issues

def process_and_load_issues(db_pool, all_issues: list, run_flag: str, jira_client):
    """Transforms Jira issue data and bulk-loads it into PostgreSQL."""
    logger.info(f"Processing {len(all_issues)} issues...")
    
    sprint_managers = db_utils.load_sprint_managers(db_pool)
    operational_epics = db_utils.load_operational_epics(db_pool)
    
    field_ids = {
        "sprint": get_custom_field_id(jira_client, "Sprint"),
        "epic_link": get_custom_field_id(jira_client, "Epic Link"),
        "parent_link": get_custom_field_id(jira_client, "Parent Link"),
        "pipeline_stage": get_custom_field_id(jira_client, "Pipeline Discovery Stage"),
        "bug_origin": get_custom_field_id(jira_client, "Origin"),
        "story_points": get_custom_field_id(jira_client, "Story Points"),
    }

    string_buffer = StringIO()
    writer = csv.writer(string_buffer)
    headers = ["epic_link", "parent_link", "oper_epic", "oper_flg", "triage_flg", "pipeline_stage",
               "bug_origin", "escaped_bug", "fix_version", "components", "issue_key", "summary",
               "issue_url", "issue_type", "sprint_name", "assignee", "status", "sprint_start_date",
               "sprint_end_date", "completed_date", "sprint_state", "labels", "sprint_owner", "export_date",
               "story_points", "run_flag", "jira_created_date", "jira_updated_date"]
    writer.writerow(headers)

    for issue in all_issues:
        row = build_row(issue, sprint_managers, operational_epics, run_flag, field_ids)
        writer.writerow(row)
        
    string_buffer.seek(0)
    
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cursor:
            sql_copy = f"COPY tbl_jira_sprint_data ({','.join(headers)}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE, DELIMITER ',')"
            cursor.copy_expert(sql=sql_copy, file=string_buffer)
            conn.commit()
            logger.info(f"Successfully loaded {len(all_issues)} records into the database.")
    except Exception as e:
        conn.rollback()
        logger.error(f"Database load failed: {e}")
    finally:
        db_pool.putconn(conn)

def build_row(issue, sprint_managers: dict, oper_epics: dict, run_flag: str, field_ids: dict) -> list:
    """Builds a single data row from a Jira issue object."""
    fields = issue.fields
    jira_server = os.getenv("JIRA_URL")
    
    sprint_data = getattr(fields, field_ids.get('sprint'), None)
    parsed_sprint = parse_sprint_data(sprint_data, sprint_managers)
    
    epic_link = getattr(fields, field_ids.get('epic_link'), None)
    parent_key = getattr(fields, 'parent', None)
    parent_link = parent_key.key if parent_key else getattr(fields, field_ids.get('parent_link'), None)
    
    pipeline_stage_val = getattr(fields, field_ids.get('pipeline_stage'), None)
    pipeline_stage = str(pipeline_stage_val.value) if hasattr(pipeline_stage_val, 'value') else ''

    bug_origin_val = getattr(fields, field_ids.get('bug_origin'), None)
    bug_origin = str(bug_origin_val.value) if hasattr(bug_origin_val, 'value') else ''

    story_points_val = getattr(fields, field_ids.get('story_points'), 0)
    story_points = float(story_points_val) if story_points_val is not None else 0.0

    return [
        epic_link, parent_link, oper_epics.get(epic_link, ''),
        'Y' if oper_parser(fields.labels) else 'N', 'Y' if triage_parser(fields.labels) else 'N',
        pipeline_stage, bug_origin, 'Y' if escaped_bug_flag(bug_origin, pipeline_stage) else 'N',
        parse_fix_version_data(fields.fixVersions), parse_component_data(fields.components),
        issue.key, fields.summary, f'{jira_server.rstrip("/")}/browse/{issue.key}',
        fields.issuetype.name, parsed_sprint['name'], fields.assignee.displayName if fields.assignee else 'Unassigned',
        fields.status.name, parsed_sprint['start_date'], parsed_sprint['end_date'],
        parsed_sprint['complete_date'], parsed_sprint['state'], parse_label_data(fields.labels),
        parsed_sprint['owner'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        story_points, run_flag, format_date(fields.created), format_date(fields.updated)
    ]

