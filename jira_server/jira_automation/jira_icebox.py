import os
import logging
from jira import JIRA
from dotenv import load_dotenv

# Use the centralized logging system
logger = logging.getLogger(__name__)

# --- Configuration Loading ---
def load_config():
    """Loads environment variables from the project root .env file."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    dotenv_path = os.path.join(project_root, '.env')
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path=dotenv_path)
    else:
        logger.warning(f".env file not found at {dotenv_path}. Script may fail if env vars are not set.")

# --- Jira Client Setup ---
def setup_jira_client():
    """Sets up and returns an authenticated Jira client."""
    jira_server = os.getenv("JIRA_URL")
    jira_api_token = os.getenv("JIRA_TOKEN")
    if not all([jira_server, jira_api_token]):
        logger.error("JIRA_URL or JIRA_TOKEN environment variables are not set.")
        return None
    
    try:
        logger.info(f"Connecting to Jira server at {jira_server}...")
        jira = JIRA(server=jira_server, token_auth=jira_api_token)
        server_info = jira.server_info()
        logger.info(f"Successfully connected to Jira version {server_info['version']}!")
        return jira
    except Exception as e:
        logger.error(f"Failed to connect to Jira: {e}")
        return None

# --- Main Logic ---
def update_stale_issues(jira_client):
    """Finds and updates stale issues by adding a label and a comment."""
    jql_query = os.getenv("JQL_QUERY")
    label_to_add = os.getenv("LABEL_TO_ADD")
    comment_to_add = os.getenv("COMMENT_TO_ADD")

    if not jql_query:
        logger.error("Missing JQL_QUERY environment variable for stale issues.")
        return

    logger.info("Running job to update stale issues...")
    logger.info(f"   Query: {jql_query}")

    try:
        stale_issues = jira_client.search_issues(jql_query, maxResults=False)
        
        if not stale_issues:
            logger.info("No stale issues found. Skipping.")
            return

        logger.info(f"Found {len(stale_issues)} stale issues to process.")
        for issue in stale_issues:
            try:
                logger.info(f"   -> Processing issue {issue.key}: {issue.fields.summary}")
                # Add the label if it doesn't already exist
                if label_to_add and label_to_add not in issue.fields.labels:
                    new_labels = issue.fields.labels + [label_to_add]
                    issue.update(fields={"labels": new_labels})
                    logger.info(f"      🏷️  Added label: '{label_to_add}'")
                elif label_to_add:
                     logger.info(f"      🏷️  Label '{label_to_add}' already exists. Skipping.")

                # Add the comment
                if comment_to_add:
                    jira_client.add_comment(issue, comment_to_add)
                    logger.info(f"      💬 Added automated comment.")
            except Exception as e:
                logger.error(f"   ❌ Failed to process issue {issue.key}: {e}")
                continue # Move to the next issue

        logger.info("Stale issue update process complete.")
    except Exception as e:
        logger.error(f"A critical error occurred while fetching stale issues: {e}")

def close_icebox_issues(jira_client):
    """Finds and closes old issues on the icebox."""
    jql_query_icebox = os.getenv("JQL_QUERY_ICEBOX")
    comment_to_add_icebox = os.getenv("COMMENT_TO_ADD_ICEBOX")

    if not jql_query_icebox:
        logger.error("Missing JQL_QUERY_ICEBOX environment variable.")
        return

    logger.info("Running job to close icebox issues...")
    logger.info(f"   Query: {jql_query_icebox}")

    try:
        icebox_issues = jira_client.search_issues(jql_query_icebox, maxResults=False)

        if not icebox_issues:
            logger.info("No icebox issues to close. Skipping.")
            return

        logger.info(f"Found {len(icebox_issues)} icebox issues to process.")
        for issue in icebox_issues:
            try:
                logger.info(f"   -> Processing issue {issue.key}: {issue.fields.summary}")

                # Find the 'Done' transition ID for this issue's workflow. This is more robust
                # than assuming the transition is just named "Done".
                transitions = jira_client.transitions(issue)
                done_transition = next((t for t in transitions if t['name'].lower() == 'done'), None)

                if done_transition:
                    # CORRECT: Use the jira_client to transition the issue using the found ID
                    jira_client.transition_issue(issue, done_transition['id'])
                    logger.info(f"      ✅ Transitioned issue {issue.key} to 'Done'")

                    # Add the comment only after a successful transition
                    if comment_to_add_icebox:
                        jira_client.add_comment(issue, comment_to_add_icebox)
                        logger.info(f"      💬 Added automated comment.")
                else:
                    logger.warning(f"      ⚠️ Could not find a 'Done' transition for issue {issue.key} (Status: {issue.fields.status.name}). Skipping transition.")

            except Exception as e:
                logger.error(f"   ❌ Failed to process issue {issue.key}: {e}")
                continue # IMPORTANT: Move to the next issue instead of crashing

        logger.info("Icebox closure process complete.")
    except Exception as e:
        logger.error(f"A critical error occurred while fetching icebox issues: {e}")

def main():
    """Main entry point for the script."""
    load_config()
    jira_client = setup_jira_client()
    if jira_client:
        update_stale_issues(jira_client)
        close_icebox_issues(jira_client)
    else:
        logger.error("Could not initialize Jira client. Aborting.")

if __name__ == "__main__":
    main()
