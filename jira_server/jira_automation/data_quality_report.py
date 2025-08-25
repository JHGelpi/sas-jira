import os
from jira import JIRA
from dotenv import load_dotenv
import logging
from datetime import datetime
import csv
import shutil

# Use absolute imports from the project's root directory
from jira_data_analysis import db_utils

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration: Field names to look up ---
FIELD_NAMES_TO_FIND = {
    "origin": "Origin",
    "pipeline_discovery": "Pipeline Discovery Stage",
    "platform_version": "Platform Version",
}

def connect_to_jira():
    """Connects to Jira using credentials from environment variables."""
    try:
        logger.info(f"⚙️ Connecting to Jira server at {os.getenv('JIRA_URL')}...")
        jira_client = JIRA(
            server=os.getenv('JIRA_URL'),
            token_auth=os.getenv('JIRA_TOKEN')
        )
        logger.info(f"✅ Successfully connected to Jira version {jira_client.server_info()['version']}!")
        return jira_client
    except Exception as e:
        logger.error(f"❌ Failed to connect to Jira: {e}")
        return None

def get_custom_field_ids(jira) -> dict:
    """Dynamically finds the custom field IDs for a given set of field names."""
    logger.info("Fetching custom field IDs from Jira...")
    custom_field_ids = {}
    try:
        all_fields = jira.fields()
        field_map = {field['name'].lower(): field['id'] for field in all_fields}
        
        for key, name in FIELD_NAMES_TO_FIND.items():
            field_id = field_map.get(name.lower())
            if field_id:
                custom_field_ids[key] = field_id
                logger.info(f"  -> Found ID for '{name}': {field_id}")
            else:
                logger.warning(f"  -> Could not find custom field named '{name}'.")
    except Exception as e:
        logger.error(f"Failed to retrieve custom fields: {e}")
    
    return custom_field_ids

def get_manager_map_from_db(db_pool) -> dict:
    """
    Fetches all users from the LDAP hierarchy table and returns a dictionary
    mapping email addresses to manager names for quick lookup.
    """
    logger.info("Fetching manager data from PostgreSQL...")
    manager_map = {}
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT email, manager_name FROM tbl_ldap_hierarchy")
            for row in cursor.fetchall():
                # Ensure email is stored in lowercase for case-insensitive matching
                if row[0]:
                    manager_map[row[0].lower()] = row[1]
        logger.info(f"Successfully loaded {len(manager_map)} user records for manager lookup.")
    except Exception as e:
        logger.error(f"Failed to fetch manager data from database: {e}")
    finally:
        db_pool.putconn(conn)
    return manager_map

def fetch_issues_for_report(jira, jql_env_var: str, report_name: str, reason: str, custom_field_ids: dict, manager_map: dict) -> list:
    """Runs a JQL query and returns a list of processed issue data, enriched with manager info."""
    jql_query = os.getenv(jql_env_var)
    if not jql_query:
        logger.warning(f"SKIPPING: Environment variable '{jql_env_var}' not set.")
        return []

    logger.info(f"--- Running query for: {report_name} ---")
    logger.info(f"  Query: {jql_query}")

    processed_issues = []
    try:
        fields_to_fetch = [
            "summary", "assignee", "fixVersions", "versions",
            *custom_field_ids.values()
        ]
        fields_to_fetch = [f for f in fields_to_fetch if f]

        issues = jira.search_issues(jql_query, fields=fields_to_fetch, maxResults=500)

        if not issues:
            logger.info("  -> No issues found matching the criteria.")
            return []

        logger.info(f"  -> Found {len(issues)} issues.")
        
        for issue in issues:
            assignee = issue.fields.assignee.displayName if issue.fields.assignee else "Unassigned"
            assignee_email = issue.fields.assignee.emailAddress.lower() if issue.fields.assignee else None
            
            # Look up the manager from the pre-loaded map
            manager_name = manager_map.get(assignee_email) if assignee_email else None

            fix_versions = ', '.join([v.name for v in issue.fields.fixVersions])
            affects_versions = ', '.join([v.name for v in issue.fields.versions])

            origin_id = custom_field_ids.get("origin")
            origin_val = getattr(issue.fields, origin_id, None) if origin_id else None
            
            pipeline_disc_id = custom_field_ids.get("pipeline_discovery")
            pipeline_disc_val = getattr(issue.fields, pipeline_disc_id, None) if pipeline_disc_id else None
            
            plat_ver_id = custom_field_ids.get("platform_version")
            plat_ver_val = getattr(issue.fields, plat_ver_id, None) if plat_ver_id else None

            processed_issues.append({
                "Reason": reason,
                "Issue Key": issue.key,
                "Issue URL": f"https://rndjira.sas.com/browse/{issue.key}",
                "Assignee": assignee,
                "Assignee Email": assignee_email,
                "Assignee Manager": manager_name,
                "Fix Version": fix_versions,
                "Origin": origin_val.value if hasattr(origin_val, 'value') else origin_val,
                "Pipeline Discovery Stage": pipeline_disc_val.value if hasattr(pipeline_disc_val, 'value') else pipeline_disc_val,
                "Platform Version": plat_ver_val,
                "Affects Version": affects_versions
            })
            
    except Exception as e:
        logger.error(f"❌ An error occurred while fetching data for report '{report_name}': {e}")
    
    return processed_issues

def write_consolidated_report(all_issues_data: list):
    """Writes the consolidated list of issues to a single CSV file."""
    if not all_issues_data:
        logger.info("No issues found across all queries. No report will be generated.")
        return

    report_dir = os.getenv('JIRA_REPORT_DIR', './reports')
    os.makedirs(report_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y-%m-%d')
    report_path = os.path.join(report_dir, f"data_quality_report_{timestamp}.csv")

    # Define the full header row, including the new columns
    header = [
        "Reason", "Issue Key", "Issue URL", "Assignee", "Assignee Email", "Assignee Manager",
        "Fix Version", "Origin", "Pipeline Discovery Stage", "Platform Version", "Affects Version"
    ]

    logger.info(f"Generating consolidated report with {len(all_issues_data)} total issues...")
    try:
        with open(report_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            writer.writerows(all_issues_data)
        logger.info(f"✅ Successfully generated consolidated report: {report_path}")

        copy_dir = os.getenv('JIRA_DQ_REPORT_COPY_DIR')
        if copy_dir:
            try:
                os.makedirs(copy_dir, exist_ok=True)
                destination_path = os.path.join(copy_dir, f"data_quality_report_{timestamp}.csv")
                shutil.copy(report_path, destination_path)
                logger.info(f"✅ Successfully copied report to: {destination_path}")
            except Exception as e:
                logger.error(f"❌ Failed to copy report to secondary directory: {e}")

    except Exception as e:
        logger.error(f"❌ Failed to write consolidated CSV report: {e}")


def main():
    """Main function to execute all data quality reports."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(dotenv_path=os.path.join(project_root, '.env'))
    
    jira_client = connect_to_jira()
    if not jira_client:
        return

    # --- NEW: Get the database connection pool and load manager data once ---
    db_pool = db_utils.get_connection_pool()
    manager_map = get_manager_map_from_db(db_pool)

    # Get all the necessary custom field IDs once
    custom_field_ids = get_custom_field_ids(jira_client)

    # Define the reports to run
    reports_to_run = {
        "JQL_MISSING_FIXVER": ("Missing Fix Version Report", "Missing Fix Version"),
        "JQL_MISSING_ORIGIN": ("Missing Origin Report", "Missing Origin"),
        "JQL_MISSING_PIPEDISC": ("Missing Pipeline Discovery Report", "Missing Pipeline Discovery Stage"),
        "JQL_MISSING_PLATVER": ("Missing Platform Version Report", "Missing Platform Version"),
        "JQL_MISSING_AFFVER": ("Missing Affects Version Report", "Missing Affects Version")
    }

    all_issues_data = []

    # Run each report and collect the results
    for jql_var, (report_name, reason) in reports_to_run.items():
        issues_found = fetch_issues_for_report(jira_client, jql_var, report_name, reason, custom_field_ids, manager_map)
        if issues_found:
            all_issues_data.extend(issues_found)
    
    # Write all collected data to a single file
    write_consolidated_report(all_issues_data)


if __name__ == "__main__":
    main()
