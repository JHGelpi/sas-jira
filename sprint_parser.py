#from jira import JIRA
import csv
from datetime import datetime

def triage_parser(labels):
    collector_label = 'collector-59dc380c'
    if collector_label in labels:
        return True
    else:
        return False

def oper_parser(labels):
    required_updates_label = 'required_updates'
    if required_updates_label in labels:
        return True
    else:
        return False

def escaped_bug_flag(origin, pipeline_stage):
    if not origin or not pipeline_stage:
        return False
    
    if 'CRP' in origin and pipeline_stage == 'Shipped':
        return True
    else: 
        return False


# Load sprint manager data from CSV into a dictionary
def load_sprint_managers(filename):
    managers = {}
    with open(filename, mode='r', encoding='utf-8') as file:
        reader = csv.reader(file)
        next(reader)  # Skip the header row if there is one
        for row in reader:
            if len(row) >= 2:
                sprint_name, manager = row[0].strip(), row[1].strip()
                managers[sprint_name] = manager
    return managers

def add_sprint_owner(sprint_managers, sprint_name):
    # sprint_owners = sprint_managers
    
    for team in sprint_managers:
        if sprint_name.startswith(team):
            #manager = sprint_managers[1]
            return sprint_managers[team]
    
    return 'No Manager'

# Load operational epic data from CSV into a dictionary
def load_oper_epics(filename):
    epics = {}
    with open(filename, mode='r', encoding='utf-8') as file:
        reader = csv.reader(file)
        next(reader)  # Skip the header row if there is one
        for row in reader:
            if len(row) >= 2:
                epic, sprint_team = row[0].strip(), row[1].strip()
                epics[sprint_team] = epic
    return epics

def add_oper_epic(epic_name):
    # Return early if epic_name is None or empty
    if not epic_name:
        return ''  

    jira_helper_folder = '/Users/wegelpi/jira/helper_files/'
    jira_oper_epics = str(jira_helper_folder) + 'operational-epics.csv'
    oper_epics = load_oper_epics(jira_oper_epics)

    # Iterate over the dictionary, checking if any value matches or is relevant to epic_name
    for project, value in oper_epics.items():
        if value == epic_name:  # Check if the value exactly matches epic_name
            return project  # Return the project key associated with the value that matches
    
    return ''  # Return empty string if no matching value is found

def parse_sprint_data(sprint_string):
    # Load the managers dictionary
    jira_helper_folder = '/Users/wegelpi/jira/helper_files/'
    jira_project_owner_file = str(jira_helper_folder) + 'jira-projects-owners.csv'
    #jira_oper_epics = jira_helper_folder & 'operational-epics.csv'

    sprint_managers = load_sprint_managers(jira_project_owner_file)
    #oper_epics = load_oper_epics(jira_oper_epics)

    # Handle None input early
    if sprint_string is None:
        return ['No Data', 'No Data', 'No Data', 'No Data', 'No Data']

    # Ensure the sprint_string is a string and not empty
    if isinstance(sprint_string, list) and sprint_string:
        sprint_string = sprint_string[0]
    elif not isinstance(sprint_string, str) or not sprint_string:
        return ['No Data', 'No Data', 'No Data', 'No Data', 'No Data']

    # Trim whitespace which might affect substring search
    sprint_string = sprint_string.strip()

    # Check for the presence of the desired pattern
    if 'state=' in sprint_string and 'startDate=' in sprint_string and 'endDate=' in sprint_string:
        # Extract the information
        state_index = sprint_string.find('state=') + len('state=')
        state = sprint_string[state_index:sprint_string.find(',', state_index)]

        sprint_name_index = sprint_string.find('name=') + len('name=')
        sprint_name = sprint_string[sprint_name_index:sprint_string.find(',', sprint_name_index)]
        
        sprint_owner = add_sprint_owner(sprint_managers, sprint_name)

        '''I need to finish up by adding in the epic value from main.py so I can reference it in
        def add_oper_epic'''
        #oper_epic = add_oper_epic(oper_epics, )

        start_index = sprint_string.find('startDate=') + len('startDate=')
        start_date = sprint_string[start_index:sprint_string.find(',', start_index)]

        end_index = sprint_string.find('endDate=') + len('endDate=')
        end_date = sprint_string[end_index:sprint_string.find(',', end_index)]

        return [state, start_date, end_date, sprint_name, sprint_owner]
    else:
        return ['No Data', 'No Data', 'No Data', 'No Data', 'No Data']  # Handle cases where format does not match
