import re
from datetime import datetime

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

def parse_sprint_data(sprint_string: str, sprint_managers: dict) -> dict:
    """
    Parses the complex sprint string from Jira's custom field into a structured dictionary.
    
    Example input: 
    "com.atlassian.greenhopper.service.sprint.Sprint@123[id=456,rapidViewId=789,state=CLOSED,name=My Sprint,startDate=...,endDate=...,completeDate=...]"
    """
    sprint_details = {
        'state': '',
        'start_date': None,
        'end_date': None,
        'complete_date': None,
        'name': '',
        'owner': 'No Manager'
    }

    if not sprint_string or not isinstance(sprint_string, str):
        return sprint_details

    # Use regex to find key=value pairs for robustness
    sprint_details.update({
        key: value for key, value in re.findall(r'(\w+)=([^,\]]+)', sprint_string)
    })
    
    # Format dates
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