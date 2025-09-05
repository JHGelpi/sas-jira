import os
import logging
from jira import JIRA
from datetime import date
from jira_data_analysis import db_utils

# Use the centralized logging system
logger = logging.getLogger(__name__)

def setup_jira_client():
    """Sets up and returns an authenticated Jira client."""
    try:
        jira_client = JIRA(
            server=os.getenv("JIRA_URL"),
            token_auth=os.getenv("JIRA_TOKEN")
        )
        logger.info(f"✅ Successfully connected to Jira version {jira_client.server_info()['version']}!")
        return jira_client
    except Exception as e:
        logger.error(f"❌ Failed to connect to Jira: {e}")
        return None

def get_custom_field_ids(jira, field_names):
    """Gets a dictionary of custom field IDs for a list of field names."""
    ids = {}
    try:
        all_fields = jira.fields()
        for field in all_fields:
            if field['name'] in field_names:
                ids[field['name']] = field['id']
    except Exception as e:
        logger.error(f"Failed to retrieve custom fields: {e}")
    return ids

def main():
    """Fetches all issues from specified projects and logs a daily snapshot."""
    jira_client = setup_jira_client()
    if not jira_client:
        return

    projects = os.getenv('JIRA_PROJECTS', '')
    if not projects:
        logger.error("JIRA_PROJECTS environment variable is not set. Aborting.")
        return

    logger.info("Starting daily bug snapshot collection...")
    
    # Dynamically find custom field IDs
    custom_field_names = ["Origin", "Pipeline Discovery Stage"]
    field_ids = get_custom_field_ids(jira_client, custom_field_names)
    origin_id = field_ids.get("Origin")
    pipeline_id = field_ids.get("Pipeline Discovery Stage")
    
    # Define all fields we need to fetch from Jira
    fields_to_fetch = [
        "issuetype", "status", "assignee", "versions", "fixVersions", "project"
    ]
    if origin_id:
        fields_to_fetch.append(origin_id)
    if pipeline_id:
        fields_to_fetch.append(pipeline_id)

    jql_query = f"project in ({projects}) AND issuetype = Bug AND updated >= -180d"
    logger.info(f"Fetching all issues with JQL: {jql_query}")

    try:
        issues = jira_client.search_issues(jql_query, fields=fields_to_fetch, maxResults=False)
        logger.info(f"Found {len(issues)} issues to process for snapshot.")
    except Exception as e:
        logger.error(f"Failed to fetch issues from Jira: {e}")
        return

    snapshot_date = date.today()
    snapshot_data = []

    for issue in issues:
        fields = issue.fields
        
        # Helper to safely get custom field values
        def get_custom_field_value(field_id):
            if not field_id:
                return None
            field_value = getattr(fields, field_id, None)
            return field_value.value if hasattr(field_value, 'value') else str(field_value) if field_value else None

        # Safely extract all data points
        affects_versions = ", ".join([v.name for v in fields.versions]) if fields.versions else None
        fix_versions = ", ".join([v.name for v in fields.fixVersions]) if fields.fixVersions else None

        snapshot_data.append((
            snapshot_date,
            issue.key,
            fields.issuetype.name if fields.issuetype else None,
            fields.status.statusCategory.name if fields.status and hasattr(fields.status, 'statusCategory') else None,
            get_custom_field_value(origin_id),
            affects_versions,
            fix_versions,
            fields.assignee.displayName if fields.assignee else None,
            get_custom_field_value(pipeline_id),
            fields.project.key if fields.project else None
        ))
        
    if not snapshot_data:
        logger.info("No data to save. Snapshot complete.")
        return

    # Bulk insert/update into the database
    db_pool = db_utils.get_connection_pool()
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cursor:
            # Use ON CONFLICT to update if a snapshot for that issue on that day already exists
            sql = """
                INSERT INTO tbl_bug_snapshots (
                    snapshot_date, issue_key, issue_type, status_category, origin,
                    affects_version, fix_version, assignee, pipeline_discovery_stage, project_key
                ) VALUES %s
                ON CONFLICT (snapshot_date, issue_key) DO UPDATE SET
                    issue_type = EXCLUDED.issue_type,
                    status_category = EXCLUDED.status_category,
                    origin = EXCLUDED.origin,
                    affects_version = EXCLUDED.affects_version,
                    fix_version = EXCLUDED.fix_version,
                    assignee = EXCLUDED.assignee,
                    pipeline_discovery_stage = EXCLUDED.pipeline_discovery_stage,
                    project_key = EXCLUDED.project_key;
            """
            from psycopg2.extras import execute_values
            execute_values(cursor, sql, snapshot_data)
            conn.commit()
            logger.info(f"Successfully inserted/updated {len(snapshot_data)} records in tbl_bug_snapshots.")
            
    except Exception as e:
        conn.rollback()
        logger.error(f"Database operation failed: {e}")
    finally:
        db_pool.putconn(conn)

if __name__ == "__main__":
    # This allows direct execution for testing
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dotenv_path = os.path.join(project_root, '.env')
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=dotenv_path)
    main()
