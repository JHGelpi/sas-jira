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

def create_rca_subtasks(jira):
    """
    Finds critical CRP bugs and creates an RCA sub-task if one doesn't already exist.
    """
    # Get configuration from environment variables
    projects = os.getenv('JIRA_PROJECTS', '')
    if not projects:
        logger.error("❌ JIRA_PROJECTS environment variable is not set. Aborting.")
        return
    
    # Get the custom field ID for 'Origin'. Based on your previous scripts, it's likely 'customfield_14504'.
    origin_field_id = os.getenv('JIRA_RCA_ORIGIN_FIELD_ID', 'customfield_14504')
    
    # Get the Issue Type ID for a "Sub-task". This must be configured correctly for your Jira instance.
    subtask_issue_type_id = os.getenv('JIRA_SUBTASK_ISSUE_TYPE_ID')
    if not subtask_issue_type_id:
        logger.error("❌ JIRA_SUBTASK_ISSUE_TYPE_ID environment variable is not set. Cannot create sub-tasks. Aborting.")
        return

    # Get the created date for filtering from the new environment variable
    jira_created_date = os.getenv('JIRA_CREATED_DATE')

    # JQL to find critical bugs from a CRP origin that don't have a "Done" status
    jql_query = (f"project in ({projects}) AND type = Bug AND priority = Critical AND statusCategory != Done AND Origin in (BRP, CRP, 'CRP PLAT', 'CRP PREM', 'CRP STND', ICRP)")
    #jql_query = (
    #    f"project in ({projects}) AND type = Bug AND priority = Critical AND "
    #    f"statusCategory != Done AND {origin_field_id} ~ 'CRP'"
    #)

    # Add the created date filter to the JQL if the environment variable is set
    if jira_created_date:
        jql_query += f" AND created >= '{jira_created_date}'"
    else:
        logger.warning("⚠️ JIRA_CREATED_DATE environment variable not set. Proceeding without a creation date filter.")


    logger.info("🔍 Running JQL query to find critical CRP bugs...")
    logger.info(f"   Query: {jql_query}")

    try:
        issues_to_process = jira.search_issues(jql_query, maxResults=100)
        
        if not issues_to_process:
            logger.info("🎉 No critical CRP bugs found that need an RCA sub-task.")
            return

        logger.info(f"Found {len(issues_to_process)} critical CRP bugs to check.")
        
        subtask_summary = "Root Cause Analysis(RCA)"
        subtask_description = os.getenv('COMMENT_TO_ADD_RCA_ST')
        
        for issue in issues_to_process:
            has_rca_subtask = False
            # Check existing sub-tasks to prevent duplicates
            if issue.fields.subtasks:
                for subtask in issue.fields.subtasks:
                    if subtask.fields.summary == subtask_summary:
                        logger.info(f"  -> Skipping {issue.key}: An RCA sub-task already exists ({subtask.key}).")
                        has_rca_subtask = True
                        break
            
            if not has_rca_subtask:
                logger.info(f"  -> Creating RCA sub-task for {issue.key}...")
                
                subtask_fields = {
                    'project': {'key': issue.fields.project.key},
                    'summary': subtask_summary,
                    'description': subtask_description,
                    'issuetype': {'id': subtask_issue_type_id},
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
