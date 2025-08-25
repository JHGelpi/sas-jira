import os
from jira import JIRA
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

def get_custom_field_id(jira, field_name: str) -> str | None:
    """Dynamically finds the custom field ID for a given field name."""
    try:
        all_fields = jira.fields()
        for field in all_fields:
            if field['name'].lower() == field_name.lower():
                logger.info(f"Found custom field ID for '{field_name}': {field['id']}")
                return field['id']
    except Exception as e:
        logger.error(f"Failed to retrieve custom fields: {e}")
    
    logger.error(f"Could not find a custom field named '{field_name}'.")
    return None

def derive_and_update_platform_version(jira):
    """
    Finds bugs where Platform Version can be derived from Affects Version/s
    and updates them.
    """
    projects = os.getenv('JIRA_PROJECTS', '')
    if not projects:
        logger.error("❌ JIRA_PROJECTS environment variable is not set. Aborting.")
        return

    # Dynamically get the custom field ID for 'Platform Version'
    platform_version_field_id = get_custom_field_id(jira, "Platform Version")
    if not platform_version_field_id:
        logger.error("❌ Could not find the 'Platform Version' custom field. Aborting.")
        return

    # JQL to find bugs where 'Platform Version' is empty but 'Affects Version/s' is not.
    jql_query = (
        f"project in ({projects}) AND type = Bug AND statusCategory != Done AND "
        f"'{platform_version_field_id}' is EMPTY AND cf[17506] is EMPTY AND affectedVersion is not EMPTY"
    )

    logger.info("🔍 Running JQL query to find bugs for platform version derivation...")
    logger.info(f"   Query: {jql_query}")

    try:
        # We only need the 'versions' field (Affects Version/s) to make decisions
        issues = jira.search_issues(jql_query, fields="versions", maxResults=False)

        if not issues:
            logger.info("🎉 No bugs found that require platform version derivation.")
            return

        logger.info(f"Found {len(issues)} bugs to process for platform version derivation.")
        
        for issue in issues:
            platform_version_to_set = None
            
            # The 'versions' field holds the 'Affects Version/s' data
            if issue.fields.versions:
                # Get the name of the first 'Affects Version' entry
                affects_version_name = issue.fields.versions[0].name.lower()

                if 'w' in affects_version_name or 'viya 3' in affects_version_name:
                    platform_version_to_set = "Viya 3.5"
                elif '94' in affects_version_name:
                    # Per logic, leave this NULL. We log and skip.
                    logger.info(f"  -> Skipping {issue.key}: Affects Version ('{affects_version_name}') contains '94'.")
                    continue
                elif '.' in affects_version_name:
                    platform_version_to_set = "Viya 4"

            if platform_version_to_set:
                logger.info(f"  -> Updating Platform Version for {issue.key} to '{platform_version_to_set}'...")
                try:
                    # Note: Platform Version is a text field, not a select list
                    issue.update(fields={platform_version_field_id: platform_version_to_set})
                    logger.info(f"✅ Successfully updated {issue.key}.")
                except Exception as e:
                    logger.error(f"❌ Failed to update {issue.key}: {e}")

    except Exception as e:
        logger.error(f"❌ An error occurred during the derivation process: {e}")


def main():
    """Main function to execute the platform version derivation."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(dotenv_path=os.path.join(project_root, '.env'))
    
    jira_client = connect_to_jira()
    if jira_client:
        derive_and_update_platform_version(jira_client)

if __name__ == "__main__":
    main()
