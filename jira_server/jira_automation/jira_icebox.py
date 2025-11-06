# jira_automation/jira_icebox.py
"""
Jira icebox automation.

This module handles stale issue management by:
1. Labeling issues that have been inactive for a long time
2. Closing issues that have been on the icebox for too long
"""

import os
from jira import JIRA
from dotenv import load_dotenv
from logging_utils import get_logger, log_section_header

logger = get_logger(__name__)

# Cache for custom field IDs to avoid repeated API calls
_field_id_cache = {}


def setup_jira_client():
    """Sets up and returns an authenticated Jira client."""
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        dotenv_path = os.path.join(project_root, '.env')
        load_dotenv(dotenv_path=dotenv_path)

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


def _get_custom_field_id(jira_client, field_name):
    """Dynamically finds and caches the custom field ID for a given field name."""
    if field_name in _field_id_cache:
        return _field_id_cache[field_name]

    try:
        all_fields = jira_client.fields()
        for field in all_fields:
            if field['name'].lower() == field_name.lower():
                field_id = field['id']
                logger.debug(f"Found custom field ID for '{field_name}': {field_id}")
                _field_id_cache[field_name] = field_id
                return field_id
    except Exception as e:
        logger.error(f"Failed to retrieve custom fields: {e}")

    logger.warning(f"Could not find a custom field named '{field_name}'")
    _field_id_cache[field_name] = None
    return None


def _find_and_apply_done_transition(jira_client, issue, comment=None):
    """
    Finds an appropriate transition to a 'Done' status category for an issue,
    sets all required fields, and applies it with an optional comment.
    All actions are performed in a single API call.

    Returns:
        True if successful, False otherwise
    """
    try:
        if issue.fields.status.statusCategory.key == 'done':
            logger.skip(f"Issue {issue.key} is already in a Done status category")
            return True

        # Get transitions with field metadata to check which fields are allowed
        transitions = jira_client.transitions(issue, expand='transitions.fields')
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
            logger.processing(f"Found transition '{transition_name}' to Closed state for {issue.key}")

            fields_payload = {}

            # Get the fields available for this specific transition
            transition_fields = done_transition.get('fields', {})

            # Set resolution only if it's allowed for this transition
            if 'resolution' in transition_fields:
                try:
                    # Get the allowed resolution values for this specific transition
                    resolution_field_meta = transition_fields.get('resolution', {})
                    allowed_resolutions = resolution_field_meta.get('allowedValues', [])

                    if allowed_resolutions:
                        # Check if "Won't Fix" is in the allowed values
                        allowed_resolution_names = {res.get('name') for res in allowed_resolutions}

                        resolution_name = None
                        if "Won't Fix" in allowed_resolution_names:
                            resolution_name = "Won't Fix"

                        if resolution_name:
                            fields_payload['resolution'] = {'name': resolution_name}
                            logger.debug(f"Will set 'Resolution' to '{resolution_name}'")
                        else:
                            logger.debug(f"'Won't Fix' not in allowed resolutions for transition '{transition_name}' on {issue.key}. Allowed: {allowed_resolution_names}")
                    else:
                        # If no allowed values specified, the transition may set resolution automatically
                        logger.debug(f"No allowed resolutions specified for transition '{transition_name}' on {issue.key} - resolution may be set automatically")

                except Exception as e:
                    logger.error(f"Could not process resolution field metadata: {e}")
            else:
                logger.debug(f"Resolution field not available for transition '{transition_name}' on {issue.key}")

            # Set the 'Doc Needed' field if configured and allowed
            doc_needed_field_name = "Doc Needed"
            doc_needed_field_id = _get_custom_field_id(jira_client, doc_needed_field_name)

            if doc_needed_field_id and doc_needed_field_id in transition_fields:
                doc_needed_value = os.getenv("JIRA_ICEBOX_DOC_NEEDED_VALUE", "No")
                fields_payload[doc_needed_field_id] = {'value': doc_needed_value}
                logger.debug(f"Will set '{doc_needed_field_name}' to '{doc_needed_value}'")
            elif doc_needed_field_id:
                logger.debug(f"'{doc_needed_field_name}' field not available for transition '{transition_name}' on {issue.key}")

            # Perform the transition with fields and comment in one atomic call
            jira_client.transition_issue(issue, transition_id, fields=fields_payload, comment=comment)
            logger.success(f"Transitioned issue {issue.key} successfully")
            if comment:
                logger.debug("Added automated comment during transition")

            return True
        else:
            logger.warning(f"Could not find a valid transition to 'Closed' state for {issue.key} (Status: {issue.fields.status.name})")
            return False

    except Exception as e:
        logger.error(f"Failed to process issue {issue.key}: {e}")
        return False


def update_stale_issues(jira_client):
    """Finds and updates issues that have been inactive for a long time."""
    log_section_header(logger, "STALE ISSUE UPDATE")
    
    jql_query = os.getenv("JQL_QUERY")
    label_to_add = os.getenv("LABEL_TO_ADD")
    comment_to_add = os.getenv("COMMENT_TO_ADD")

    if not jql_query:
        logger.warning("No JQL_QUERY found in environment. Skipping stale issue update")
        return

    logger.searching("Running JQL query to find stale issues")
    logger.debug(f"Query: {jql_query}")
    
    stale_issues = jira_client.search_issues(jql_query, maxResults=False)

    if not stale_issues:
        logger.complete("No stale issues found")
        return

    logger.info(f"Found {len(stale_issues)} stale issues to process")
    
    processed_count = 0
    for issue in stale_issues:
        try:
            logger.processing(f"Processing issue {issue.key}: {issue.fields.summary}")
            
            if label_to_add and label_to_add not in issue.fields.labels:
                issue.add_field_value("labels", label_to_add)
                logger.success(f"Added label '{label_to_add}' to {issue.key}")
            
            if comment_to_add:
                jira_client.add_comment(issue, comment_to_add)
                logger.success(f"Added automated comment to {issue.key}")
            
            processed_count += 1
            
        except Exception as e:
            logger.error(f"Failed to process stale issue {issue.key}: {e}")
    
    logger.complete(f"Stale issue update complete: {processed_count} issues processed")


def close_icebox_issues(jira_client):
    """Finds and closes issues that have been on the icebox for too long."""
    log_section_header(logger, "ICEBOX ISSUE CLOSURE")
    
    jql_query = os.getenv("JQL_QUERY_ICEBOX")
    comment_to_add = os.getenv("COMMENT_TO_ADD_ICEBOX")

    if not jql_query:
        logger.warning("No JQL_QUERY_ICEBOX found in environment. Skipping icebox closure")
        return

    logger.searching("Running JQL query to find icebox issues")
    logger.debug(f"Query: {jql_query}")
    
    icebox_issues = jira_client.search_issues(jql_query, fields="*all", maxResults=False)

    if not icebox_issues:
        logger.complete("No icebox issues found to close")
        return

    logger.info(f"Found {len(icebox_issues)} icebox issues to process")
    
    closed_count = 0
    skipped_count = 0
    
    for issue in icebox_issues:
        try:
            logger.processing(f"Processing parent issue {issue.key}: {issue.fields.summary}")
            
            all_subtasks_closed = True
            if issue.fields.subtasks:
                logger.info(f"Found {len(issue.fields.subtasks)} sub-task(s) for {issue.key}. Closing them first")
                for subtask in issue.fields.subtasks:
                    if not _find_and_apply_done_transition(jira_client, subtask, comment=comment_to_add):
                        all_subtasks_closed = False
                        logger.error(f"Could not close sub-task {subtask.key}. Aborting closure for parent {issue.key}")
                        break
            
            if all_subtasks_closed:
                logger.info(f"All sub-tasks for {issue.key} are closed (or none existed). Proceeding to close parent")
                if _find_and_apply_done_transition(jira_client, issue, comment=comment_to_add):
                    closed_count += 1
                else:
                    skipped_count += 1
            else:
                skipped_count += 1

        except Exception as e:
            logger.exception(f"An unexpected error occurred while processing parent issue {issue.key}: {e}")
            skipped_count += 1
    
    logger.complete(f"Icebox process complete: {closed_count} closed, {skipped_count} skipped")


def main():
    """Main function to run the Jira automation jobs."""
    jira_client = setup_jira_client()
    if not jira_client:
        return

    update_stale_issues(jira_client)
    close_icebox_issues(jira_client)


if __name__ == "__main__":
    from logging_config import setup_logging
    setup_logging()
    main()