import os
from jira import JIRA
from dotenv import load_dotenv
import logging
from datetime import datetime
import csv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration: Field names to look up ---
# These are the display names of the custom fields in Jira.
# "Affects Version" has been removed as it's a system field.
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
        # Create a map of lowercased field names to their IDs for easy lookup
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

def generate_report_for_jql(jira, jql_env_var: str, report_name: str, custom_field_ids: dict):
    """Runs a JQL query from an environment variable and generates a CSV report."""
    jql_query = os.getenv(jql_env_var)
    if not jql_query:
        logger.warning(f"SKIPPING: Environment variable '{jql_env_var}' not set.")
        return

    logger.info(f"--- Running report: {report_name} ---")
    logger.info(f"  Query: {jql_query}")

    report_dir = os.getenv('JIRA_REPORT_DIR', './reports')
    os.makedirs(report_dir, exist_ok=True)

    try:
        # Construct the list of fields to fetch from Jira
        fields_to_fetch = [
            "summary", "assignee", "fixVersions", "versions", # "versions" is the system field for "Affects Version/s"
            *custom_field_ids.values() # Unpack all found custom field IDs
        ]
        # Filter out any None values if a custom field wasn't found
        fields_to_fetch = [f for f in fields_to_fetch if f]

        issues = jira.search_issues(jql_query, fields=fields_to_fetch, maxResults=500)

        if not issues:
            logger.info("  -> No issues found matching the criteria.")
            return

        logger.info(f"  -> Found {len(issues)} issues. Generating CSV report...")
        
        timestamp = datetime.now().strftime('%Y-%m-%d')
        report_path = os.path.join(report_dir, f"{report_name}_{timestamp}.csv")

        with open(report_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # --- FIX: Use .get() for safer dictionary access when creating the header ---
            writer.writerow([
                "Issue Key", "Issue URL", "Assignee", "Fix Version",
                FIELD_NAMES_TO_FIND.get("origin", "Origin"),
                FIELD_NAMES_TO_FIND.get("pipeline_discovery", "Pipeline Discovery Stage"),
                FIELD_NAMES_TO_FIND.get("platform_version", "Platform Version"),
                "Affects Version" # Hardcoded header for the system field
            ])

            # Write data rows
            for issue in issues:
                assignee = issue.fields.assignee.displayName if issue.fields.assignee else "Unassigned"
                fix_versions = ', '.join([v.name for v in issue.fields.fixVersions])
                affects_versions = ', '.join([v.name for v in issue.fields.versions])

                origin_id = custom_field_ids.get("origin")
                origin_val = getattr(issue.fields, origin_id, None) if origin_id else None
                
                pipeline_disc_id = custom_field_ids.get("pipeline_discovery")
                pipeline_disc_val = getattr(issue.fields, pipeline_disc_id, None) if pipeline_disc_id else None
                
                plat_ver_id = custom_field_ids.get("platform_version")
                plat_ver_val = getattr(issue.fields, plat_ver_id, None) if plat_ver_id else None

                writer.writerow([
                    issue.key,
                    f"https://rndjira.sas.com/browse/{issue.key}",
                    assignee,
                    fix_versions,
                    origin_val.value if hasattr(origin_val, 'value') else origin_val,
                    pipeline_disc_val.value if hasattr(pipeline_disc_val, 'value') else pipeline_disc_val,
                    plat_ver_val,
                    affects_versions
                ])
        
        logger.info(f"✅ Successfully generated report: {report_path}")

    except Exception as e:
        logger.error(f"❌ An error occurred while generating report '{report_name}': {e}")


def main():
    """Main function to execute all data quality reports."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(dotenv_path=os.path.join(project_root, '.env'))
    
    jira_client = connect_to_jira()
    if not jira_client:
        return

    # Get all the necessary custom field IDs once
    custom_field_ids = get_custom_field_ids(jira_client)

    # Define the reports to run
    reports_to_run = {
        "JQL_MISSING_FIXVER": "missing_fix_version",
        "JQL_MISSING_ORIGIN": "missing_origin",
        "JQL_MISSING_PIPEDISC": "missing_pipeline_discovery",
        "JQL_MISSING_PLATVER": "missing_platform_version",
        "JQL_MISSING_AFFVER": "missing_affects_version"
    }

    # Run each report
    for jql_var, report_name in reports_to_run.items():
        generate_report_for_jql(jira_client, jql_var, report_name, custom_field_ids)

if __name__ == "__main__":
    main()
