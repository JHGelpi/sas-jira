import os
import logging
from jira import JIRA
from dotenv import load_dotenv

# Use the centralized logging system
logger = logging.getLogger(__name__)

# Cache for custom field IDs to avoid repeated API calls
_field_id_cache = {}

def setup_jira_client():
    """Sets up and returns an authenticated Jira client."""
    try:
        # Get the absolute path to the project root to reliably find the .env file
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        dotenv_path = os.path.join(project_root, '.env')
        load_dotenv(dotenv_path=dotenv_path)

        jira_client = JIRA(
            server=os.getenv('JIRA_URL'),
            token_auth=os.getenv('JIRA_TOKEN')
        )
        logger.info(f"✅ Successfully connected to Jira version {jira_client.server_info()['version']}!")
        return jira_client
    except Exception as e:
        logger.error(f"❌ Failed to connect to Jira: {e}")
        return None

def _get_custom_field_id(jira_client, field_name):
    """Dynamically finds and caches the custom field ID for a given field name."""
    if field_name in _field_id_cache:
        return _field_id_cache[field_name]

    try:
        all_fields = jira_client.fields()
        for field in all_fields:
            if field['name'].lower() == field_name.lower():
                field_id = field['id']
                logger.info(f"      -> Found custom field ID for '{field_name}': {field_id}")
                _field_id_cache[field_name] = field_id
                return field_id
    except Exception as e:
        logger.error(f"      -> Failed to retrieve custom fields: {e}")

    logger.warning(f"      -> Could not find a custom field named '{field_name}'.")
    _field_id_cache[field_name] = None # Cache the failure too
    return None


def _find_and_apply_done_transition(jira_client, issue, comment=None):
    """
    Finds an appropriate transition to a 'Done' status category for an issue,
    sets all required fields by inspecting the transition's requirements, and applies it.
    All actions (transition, fields, comment) are performed in a single API call.
    Returns True if successful, False otherwise.
    """
    try:
        if issue.fields.status.statusCategory.key == 'done':
            logger.info(f"      -> Issue {issue.key} is already in a Done status category. Skipping.")
            return True

        transitions = jira_client.transitions(issue)
        done_transition = None
        for t in transitions:
            destination_status = t.get('to', {})
            status_category = destination_status.get('statusCategory', {})
            if status_category.get('key') == 'done':
                if destination_status.get('name', '').lower() == 'closed':
                    done_transition = t
                    break
        
        if done_transition:
            transition_id = done_transition['id']
            transition_name = done_transition['name']
            logger.info(f"      ➡️  Found transition '{transition_name}' to a Closed state for {issue.key}. Applying...")

            fields_payload = {}
            
            # --- FIX: Assume resolution is required, as the API error indicates it is. ---
            # The transition metadata can sometimes be incomplete. We will trust the API error.
            try:
                all_resolutions = jira_client.resolutions()
                allowed_names = {res.name for res in all_resolutions}
                
                resolution_name = None
                # --- CHANGE: Prioritize "Won't Fix" as requested ---
                if "Won't Fix" in allowed_names:
                    resolution_name = "Won't Fix"
                
                if resolution_name:
                    fields_payload['resolution'] = {'name': resolution_name}
                    logger.info(f"      -> Will attempt to set 'Resolution' to '{resolution_name}'")
                else:
                    logger.warning(f"     ⚠️ Could not find a suitable global resolution ('Won't Fix'). This may fail.")

            except Exception as e:
                logger.error(f"      -> Could not fetch global resolutions: {e}. Proceeding without setting resolution.")


            # Set the 'Doc Needed' field (if found and configured)
            doc_needed_field_name = "Doc Needed"
            doc_needed_field_id = _get_custom_field_id(jira_client, doc_needed_field_name)
            
            if doc_needed_field_id:
                doc_needed_value = os.getenv("JIRA_ICEBOX_DOC_NEEDED_VALUE", "No")
                fields_payload[doc_needed_field_id] = {'value': doc_needed_value}
                logger.info(f"      -> Will set '{doc_needed_field_name}' to '{doc_needed_value}'")

            # Perform the transition, including all required fields and the comment in one atomic call
            jira_client.transition_issue(issue, transition_id, fields=fields_payload, comment=comment)
            logger.info(f"      ✅ Transitioned issue {issue.key} successfully.")
            if comment:
                logger.info("      💬 Added automated comment during transition.")

            return True
        else:
            logger.warning(f"      ⚠️ Could not find a valid transition to a 'Closed' state for issue {issue.key} (Status: {issue.fields.status.name}). Skipping transition.")
            return False
            
    except Exception as e:
        logger.error(f"      ❌ Failed to process issue {issue.key}: {e}")
        return False

def update_stale_issues(jira_client):
    """Finds and updates issues that have been inactive for a long time."""
    logger.info("Running job to update stale issues...")
    jql_query = os.getenv("JQL_QUERY")
    label_to_add = os.getenv("LABEL_TO_ADD")
    comment_to_add = os.getenv("COMMENT_TO_ADD")

    if not jql_query:
        logger.warning("No JQL_QUERY found in environment. Skipping stale issue update.")
        return

    logger.info(f"   Query: {jql_query}")
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
            logger.error(f"      ❌ Failed to process stale issue {issue.key}: {e}")

def close_icebox_issues(jira_client):
    """Finds and closes issues that have been on the icebox for too long."""
    logger.info("Running job to close icebox issues...")
    jql_query = os.getenv("JQL_QUERY_ICEBOX")
    comment_to_add = os.getenv("COMMENT_TO_ADD_ICEBOX")

    if not jql_query:
        logger.warning("No JQL_QUERY_ICEBOX found in environment. Skipping icebox closure.")
        return

    logger.info(f"   Query: {jql_query}")
    icebox_issues = jira_client.search_issues(jql_query, fields="*all", maxResults=False)

    if not icebox_issues:
        logger.info("No icebox issues found to close.")
        return

    logger.info(f"Found {len(icebox_issues)} icebox issues to process.")
    for issue in icebox_issues:
        try:
            logger.info(f"   -> Processing parent issue {issue.key}: {issue.fields.summary}")
            
            all_subtasks_closed = True
            if issue.fields.subtasks:
                logger.info(f"      -> Found {len(issue.fields.subtasks)} sub-task(s). Closing them first...")
                # Pass the comment to the sub-task transition as well
                for subtask in issue.fields.subtasks:
                    if not _find_and_apply_done_transition(jira_client, subtask, comment=comment_to_add):
                        all_subtasks_closed = False
                        logger.error(f"      ❌ Could not close sub-task {subtask.key}. Aborting closure for parent {issue.key}.")
                        break 
            
            if all_subtasks_closed:
                logger.info(f"      -> All sub-tasks for {issue.key} are closed (or none existed). Proceeding to close parent.")
                _find_and_apply_done_transition(jira_client, issue, comment=comment_to_add)

        except Exception as e:
            logger.error(f"      ❌ An unexpected error occurred while processing parent issue {issue.key}: {e}")

    logger.info("Icebox process complete.")


def main():
    """Main function to run the Jira automation jobs."""
    jira_client = setup_jira_client()
    if not jira_client:
        return

    update_stale_issues(jira_client)
    close_icebox_issues(jira_client)

if __name__ == "__main__":
    main()

