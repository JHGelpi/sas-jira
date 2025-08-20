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

# --- NEW: A cache to store sub-task IDs per project ---
PROJECT_SUBTASK_ID_CACHE = {}

def get_subtask_issue_type_id(jira, project_key: str) -> str | None:
    """
    Finds the correct Sub-task issue type ID for a given project.
    Results are cached to avoid repeated API calls.
    """
    # Return the cached ID if we've already found it for this project
    if project_key in PROJECT_SUBTASK_ID_CACHE:
        return PROJECT_SUBTASK_ID_CACHE[project_key]

    try:
        logger.info(f"Querying issue types for project '{project_key}'...")
        # Get the metadata for all issue types available in the specified project
        project_meta = jira.project(project_key)
        
        for issue_type in project_meta.issueTypes:
            # A sub-task is identified by the 'subtask' boolean flag
            if issue_type.subtask:
                logger.info(f"Found Sub-task ID for project '{project_key}': {issue_type.id} (Name: '{issue_type.name}')")
                # Cache the result for next time
                PROJECT_SUBTASK_ID_CACHE[project_key] = issue_type.id
                return issue_type.id
        
        logger.error(f"No sub-task issue type found for project '{project_key}'.")
        return None
    except Exception as e:
        logger.error(f"Could not retrieve issue types for project '{project_key}': {e}")
        return None


def create_rca_subtasks(jira):
    """
    Finds critical CRP bugs and creates an RCA sub-task if one doesn't already exist.
    """
    # Get configuration from environment variables
    projects = os.getenv('JIRA_PROJECTS', '')
    if not projects:
        logger.error("❌ JIRA_PROJECTS environment variable is not set. Aborting.")
        return
    
    origin_field_name = os.getenv('JIRA_RCA_ORIGIN_FIELD_NAME')
    if not origin_field_name:
        logger.error("❌ JIRA_RCA_ORIGIN_FIELD_NAME environment variable not set. Aborting.")
        return
        
    origin_field_id = get_custom_field_id(jira, origin_field_name)
    if not origin_field_id:
        logger.error(f"Aborting because the '{origin_field_name}' field could not be found.")
        return

    jira_created_date = os.getenv('JIRA_CREATED_DATE')

    # JQL to find critical bugs from a CRP origin that don't have a "Done" status
    jql_query = (
        f"project in ({projects}) AND type = Bug AND priority = Critical AND "
        #f"statusCategory != Done AND \"{origin_field_name}\" ~ 'CRP'"
        f"statusCategory != Done AND \"{origin_field_name}\" in(BRP, CRP, 'CRP PLAT', 'CRP PREM', 'CRP STND', ICRP)"
    )

    if jira_created_date:
        jql_query += f" AND created >= '{jira_created_date}'"
    else:
        logger.warning("⚠️ JIRA_CREATED_DATE environment variable not set. Proceeding without a creation date filter.")


    logger.info("🔍 Running JQL query to find critical CRP bugs...")
    logger.info(f"   Query: {jql_query}")

    try:
        # Explicitly request fields needed for logging and sub-task creation
        fields_to_request = ["summary", "status", "assignee", "subtasks", "project"]
        issues_to_process = jira.search_issues(jql_query, maxResults=100, fields=fields_to_request)
        
        if not issues_to_process:
            logger.info("🎉 No critical CRP bugs found that need an RCA sub-task.")
            return

        logger.info(f"Found {len(issues_to_process)} critical CRP bugs to check.")
        
        subtask_summary = "Root Cause Analysis(RCA)"
        subtask_description = os.getenv('COMMENT_TO_ADD_RCA_ST')
        
        for issue in issues_to_process:
            assignee_name = issue.fields.assignee.displayName if issue.fields.assignee else "Unassigned"
            logger.info(f"Processing Ticket: {issue.key} | Summary: '{issue.fields.summary}' | Status: '{issue.fields.status.name}' | Assignee: {assignee_name}")

            has_rca_subtask = False
            # Check existing sub-tasks to prevent duplicates
            if issue.fields.subtasks:
                for subtask in issue.fields.subtasks:
                    if subtask.fields.summary == subtask_summary:
                        logger.info(f"  -> Skipping {issue.key}: An RCA sub-task already exists ({subtask.key}).")
                        has_rca_subtask = True
                        break
            
            if not has_rca_subtask:
                # --- NEW: Get the correct sub-task ID for this specific project ---
                project_key = issue.fields.project.key
                subtask_id_for_project = get_subtask_issue_type_id(jira, project_key)

                if not subtask_id_for_project:
                    logger.error(f"  -> Skipping {issue.key}: Could not determine the sub-task ID for project '{project_key}'.")
                    continue

                logger.info(f"  -> Creating RCA sub-task for {issue.key} using issue type ID {subtask_id_for_project}...")
                
                subtask_fields = {
                    'project': {'key': project_key},
                    'summary': subtask_summary,
                    'description': subtask_description,
                    'issuetype': {'id': subtask_id_for_project},
                    'parent': {'key': issue.key},
                }
                
                try:
                    new_subtask = jira.create_issue(fields=subtask_fields)
                    logger.info(f"✅ Successfully created sub-task {new_subtask.key} for parent {issue.key}.")
                except Exception as e:
                    logger.error(f"❌ Failed to create sub-task for {issue.key}: {e}")

    except Exception as e:
        logger.error(f"❌ An error occurred while searching for issues: {e}")


def main():
    """Main function to execute the RCA sub-task creation."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(dotenv_path=os.path.join(project_root, '.env'))
    
    jira_client = connect_to_jira()
    if jira_client:
        create_rca_subtasks(jira_client)

if __name__ == "__main__":
    main()
