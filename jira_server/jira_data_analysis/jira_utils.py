import re
from datetime import datetime
from dateutil.parser import parse as parse_date

# --- NEW: Cache for custom field IDs to avoid repeated API calls ---
_field_id_cache = {}

def get_custom_field_id(jira_client, field_name: str) -> str | None:
    """
    Dynamically finds and caches the custom field ID for a given field name.
    This makes the scripts resilient to changes in Jira configuration.
    """
    if field_name in _field_id_cache:
        return _field_id_cache[field_name]

    try:
        all_fields = jira_client.fields()
        for field in all_fields:
            if field['name'].lower() == field_name.lower():
                field_id = field['id']
                # Cache the found ID for future use in this run
                _field_id_cache[field_name] = field_id
                return field_id
    except Exception as e:
        print(f"Error retrieving custom fields: {e}")

    print(f"WARNING: Could not find a custom field named '{field_name}'.")
    _field_id_cache[field_name] = None # Cache the failure to avoid re-checking
    return None

def format_date(date_str: str) -> str | None:
    """
    Parses various date string formats from Jira and returns a 'YYYY-MM-DD' string.
    Returns None if the input is invalid or empty.
    """
    if not date_str or date_str == '<null>':
        return None
    try:
        # Handles formats like '2023-04-09T10:30:00.123+0000'
        return parse_date(date_str).strftime('%Y-%m-%d')
    except (TypeError, ValueError):
        # Fallback for other potential formats or invalid data
        return None

def parse_sprint_data(sprint_data, sprint_managers: dict) -> dict:
    """
    Parses sprint data, handling both the legacy string format and the new
    list-of-strings format from the Jira API.
    """
    sprint_details = {
        'state': '', 'start_date': None, 'end_date': None,
        'complete_date': None, 'name': '', 'owner': 'No Manager'
    }

    if not sprint_data:
        return sprint_details

    string_to_parse = None
    # --- FIX: Correctly handle the list-of-strings format ---
    if isinstance(sprint_data, list) and sprint_data:
        # The API is returning a list containing a single string.
        # We extract that string to be parsed.
        string_to_parse = sprint_data[-1]
    elif isinstance(sprint_data, str):
        # Handle the case where it might just be a string
        string_to_parse = sprint_data

    # Proceed with parsing only if we have a valid string
    if string_to_parse and isinstance(string_to_parse, str):
        found_details = {
            key: value for key, value in re.findall(r'(\w+)=([^,\]]+)', string_to_parse)
        }
        sprint_details.update(found_details)
        sprint_details['start_date'] = format_date(sprint_details.get('startDate'))
        sprint_details['end_date'] = format_date(sprint_details.get('endDate'))
        sprint_details['complete_date'] = format_date(sprint_details.get('completeDate'))

    # Determine sprint owner
    sprint_name = sprint_details.get('name', '')
    for team, manager in sprint_managers.items():
        if sprint_name.startswith(team):
            sprint_details['owner'] = manager
            break
            
    return sprint_details

def parse_label_data(labels: list) -> str:
    """Joins a list of labels into a single pipe-separated string."""
    if not labels:
        return ''
    return '|'.join(str(label) for label in labels)

def parse_component_data(components: list) -> str:
    """Joins a list of component objects into a single pipe-separated string of their names."""
    if not components:
        return ''
    return '|'.join(comp.name for comp in components if hasattr(comp, 'name'))

def parse_fix_version_data(fix_versions: list) -> str:
    """Joins a list of fixVersion objects into a single pipe-separated string of their names."""
    if not fix_versions:
        return ''
    return '|'.join(fv.name for fv in fix_versions if hasattr(fv, 'name'))

def triage_parser(labels: list) -> bool:
    """Checks if a specific triage label exists in the list of labels."""
    return 'collector-59dc380c' in labels

def oper_parser(labels: list) -> bool:
    """Checks if a specific operational label exists in the list of labels."""
    return 'required_updates' in labels

def escaped_bug_flag(origin: str, pipeline_stage: str) -> bool:
    """Determines if a bug is an 'escaped bug' based on its origin and stage."""
    if not origin or not pipeline_stage:
        return False
    # Example logic: bug is considered "escaped" if it originated
    # from a customer-facing phase and was shipped.
    if 'CRP' in origin and pipeline_stage == 'Shipped':
        return True
    return False

