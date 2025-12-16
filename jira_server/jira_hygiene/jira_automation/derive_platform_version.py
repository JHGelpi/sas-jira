# jira_automation/derive_platform_version.py
"""
Platform version derivation automation.

This module automatically populates the Platform Version field based on
the Affects Version/s field using business logic rules.
"""

import os
from jira import JIRA
from dotenv import load_dotenv
from logging_utils import get_logger, log_section_header

logger = get_logger(__name__)


def connect_to_jira():
    """Connects to Jira using credentials from environment variables."""
    try:
        jira_url = os.getenv('JIRA_URL')
        logger.connecting(f"Connecting to Jira server at {jira_url}")
        
        jira_client = JIRA(
            server=jira_url,
            token_auth=os.getenv('JIRA_TOKEN')
        )
        
        version = jira_client.server_info()['version']
        logger.success(f"Connected to Jira version {version}")
        return jira_client
        
    except Exception as e:
        logger.error(f"Failed to connect to Jira: {e}")
        return None


def get_custom_field_id(jira, field_name: str) -> str | None:
    """Dynamically finds the custom field ID for a given field name."""
    try:
        all_fields = jira.fields()
        for field in all_fields:
            if field['name'].lower() == field_name.lower():
                logger.debug(f"Found custom field ID for '{field_name}': {field['id']}")
                return field['id']
    except Exception as e:
        logger.error(f"Failed to retrieve custom fields: {e}")
    
    logger.error(f"Could not find a custom field named '{field_name}'")
    return None


def derive_and_update_platform_version(jira):
    """
    Finds bugs where Platform Version can be derived from Affects Version/s
    and updates them.
    """
    log_section_header(logger, "PLATFORM VERSION DERIVATION")
    
    projects = os.getenv('JIRA_PROJECTS', '')
    if not projects:
        logger.error("JIRA_PROJECTS environment variable is not set")
        return

    # Dynamically get the custom field ID for 'Platform Version'
    platform_version_field_name = "Platform Version"
    platform_version_field_id = get_custom_field_id(jira, platform_version_field_name)
    if not platform_version_field_id:
        logger.error(f"Could not find the '{platform_version_field_name}' custom field")
        return

    # Query finds bugs that meet the criteria and are either:
    # 1. Not in a 'Done' state, OR
    # 2. Have been updated in the last 3 days (regardless of state)
    jql_query = (
        f'project in ({projects}) AND type = Bug AND '
        f'"{platform_version_field_name}" is EMPTY AND affectedVersion is not EMPTY AND '
        f'(statusCategory != Done OR updated >= -3d)'
    )

    logger.searching("Running JQL query to find bugs for platform version derivation")
    logger.debug(f"Query: {jql_query}")

    try:
        issues = jira.search_issues(jql_query, fields="versions", maxResults=False)

        if not issues:
            logger.complete("No bugs found that require platform version derivation")
            return

        logger.info(f"Found {len(issues)} bugs to process for platform version derivation")
        
        updated_count = 0
        skipped_count = 0
        
        for issue in issues:
            platform_version_to_set = None
            
            # The 'versions' field holds the 'Affects Version/s' data
            if issue.fields.versions:
                affects_version_name = issue.fields.versions[0].name.lower()

                if 'w' in affects_version_name or 'Viya 3' in affects_version_name:
                    platform_version_to_set = "Viya 3.5"
                elif '94' in affects_version_name:
                    logger.skip(f"Skipping {issue.key}: Affects Version ('{affects_version_name}') contains '94'")
                    skipped_count += 1
                    continue
                elif '.' in affects_version_name:
                    platform_version_to_set = "Viya 4"

            if platform_version_to_set:
                logger.processing(f"Updating Platform Version for {issue.key} to '{platform_version_to_set}'")
                try:
                    update_data = {'value': platform_version_to_set}
                    issue.update(fields={platform_version_field_id: update_data})
                    logger.success(f"Updated {issue.key}")
                    updated_count += 1
                except Exception as e:
                    logger.error(f"Failed to update {issue.key}: {e}")

        logger.complete(f"Platform version derivation complete: {updated_count} updated, {skipped_count} skipped")

    except Exception as e:
        logger.exception(f"An error occurred during the derivation process: {e}")


def main():
    """Main function to execute the platform version derivation."""
    jira_client = connect_to_jira()
    if jira_client:
        derive_and_update_platform_version(jira_client)


if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(dotenv_path=os.path.join(project_root, '.env'))
    
    from logging_config import setup_logging
    setup_logging()
    
    main()