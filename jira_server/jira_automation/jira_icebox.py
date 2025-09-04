import os
from jira import JIRA
from dotenv import load_dotenv
import logging
import sys

# Use the centralized logging system
logger = logging.getLogger(__name__)

def setup_jira_client():
    """Sets up and returns an authenticated Jira client."""
    try:
        jira_client = JIRA(
            server=os.getenv("JIRA_URL"),
            token_auth=os.getenv("JIRA_TOKEN")
        )
        # Verify connection by getting server info
        server_info = jira_client.server_info()
        logger.info(f"✅ Successfully connected to Jira version {server_info['version']}!")
        return jira_client
    except Exception as e:
        logger.error(f"❌ Failed to connect to Jira: {e}")
        return None

def _find_and_apply_done_transition(jira_client, issue, comment=None):
    """
    Helper function to find an appropriate "Done" transition and apply it.
    Returns True on success, False on failure.
    """
    # --- FIX IS HERE ---
    # First, check if the issue is already in a 'Done' state to avoid unnecessary work
    # issue.fields.status.statusCategory is an object, so we use attribute access (.key)
    if issue.fields.status.statusCategory.key == 'done':
        logger.info(f"      -> Issue {issue.key} is already in a Done status category. Skipping.")
        return True

    transitions = jira_client.transitions(issue)
    done_transition = None
    for t in transitions:
        # The transition data 't' is a dictionary, so we use key access here
        if t['to']['statusCategory']['key'] == 'done':
            done_transition = t
            break  # Found a suitable transition

    if done_transition:
        transition_id = done_transition['id']
        transition_name = done_transition['name']
        logger.info(f"      ➡️  Found transition '{transition_name}' for {issue.key}. Applying...")
        jira_client.transition_issue(issue, transition_id)
        logger.info(f"      ✅ Transitioned issue {issue.key} successfully.")
        if comment:
            jira_client.add_comment(issue, comment)
            logger.info("      💬 Added automated comment.")
        return True
    else:
        logger.warning(f"      ⚠️ Could not find a valid transition to a 'Done' category for issue {issue.key} (Status: {issue.fields.status.name}).")
        return False

def update_stale_issues(jira_client):
    """Finds and updates issues that have become stale."""
    logger.info("Running job to update stale issues...")
    jql_query = os.getenv("JQL_QUERY")
    label_to_add = os.getenv("LABEL_TO_ADD")
    comment_to_add = os.getenv("COMMENT_TO_ADD")

    if not jql_query:
        logger.warning("No JQL_QUERY found in environment variables. Skipping stale issue update.")
        return

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
                if label_to_add and label_to_add not in issue.fields.labels:
                    issue.add_field_value("labels", label_to_add)
                    logger.info(f"      🏷️  Added label: '{label_to_add}'")
                if comment_to_add:
                    jira_client.add_comment(issue, comment_to_add)
                    logger.info("      💬 Added automated comment.")
            except Exception as e:
                logger.error(f"      ❌ Failed to process issue {issue.key}: {e}")

    except Exception as e:
        logger.error(f"❌ An error occurred while fetching stale issues: {e}")


def close_icebox_issues(jira_client):
    """Finds and closes issues that are on the icebox, handling sub-tasks first."""
    logger.info("Running job to close icebox issues...")
    jql_query_icebox = os.getenv("JQL_QUERY_ICEBOX")
    comment_to_add_icebox = os.getenv("COMMENT_TO_ADD_ICEBOX")

    if not jql_query_icebox:
        logger.warning("No JQL_QUERY_ICEBOX found in environment variables. Skipping icebox closure.")
        return

    logger.info(f"   Query: {jql_query_icebox}")
    try:
        # We must fetch the subtasks field to check for them
        icebox_issues = jira_client.search_issues(jql_query_icebox, fields="summary,status,subtasks", maxResults=False)
        if not icebox_issues:
            logger.info("No icebox issues found to close.")
            return

        logger.info(f"Found {len(icebox_issues)} icebox issues to process.")
        for issue in icebox_issues:
            try:
                logger.info(f"   -> Processing parent issue {issue.key}: {issue.fields.summary}")

                # 1. Handle Sub-tasks first
                if issue.fields.subtasks:
                    logger.info(f"      -> Found {len(issue.fields.subtasks)} sub-task(s). Closing them first...")
                    all_subtasks_closed = True
                    for subtask in issue.fields.subtasks:
                        # The subtask object from the parent is partial, so we fetch the full object
                        full_subtask = jira_client.issue(subtask.key, fields="status")
                        if not _find_and_apply_done_transition(jira_client, full_subtask):
                            all_subtasks_closed = False
                            logger.error(f"      ❌ Failed to close sub-task {subtask.key}, cannot proceed with parent issue {issue.key}.")
                            break  # Stop processing sub-tasks for this parent

                    if not all_subtasks_closed:
                        logger.warning(f"      -> Halting closure of parent {issue.key} because one or more sub-tasks could not be closed.")
                        continue  # Move to the next parent issue in the main loop

                # 2. Close the parent issue if all sub-tasks are handled
                logger.info(f"      -> All sub-tasks for {issue.key} are closed (or none existed). Proceeding to close parent.")
                _find_and_apply_done_transition(jira_client, issue, comment_to_add_icebox)

            except Exception as e:
                logger.error(f"      ❌ An unexpected error occurred while processing parent issue {issue.key}: {e}")

    except Exception as e:
        logger.error(f"❌ An error occurred while fetching icebox issues: {e}")

def main():
    """Main function to run both stale issue updates and icebox closures."""
    jira_client = setup_jira_client()
    if not jira_client:
        return

    update_stale_issues(jira_client)
    close_icebox_issues(jira_client)
    logger.info("Icebox process complete.")


if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dotenv_path = os.path.join(project_root, '.env')
    load_dotenv(dotenv_path=dotenv_path)
    main()

