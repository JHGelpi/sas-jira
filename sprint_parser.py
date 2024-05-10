#from jira import JIRA
import csv
from datetime import datetime

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

#def parse_sprint_data(sprint_string):
    # Initial data parsing
    #parsed_data = parse_sprint_data_basic(sprint_string)
    # Load the managers dictionary
    #sprint_managers = load_sprint_managers(jira_project_owner_file)
    #sprint_name = parsed_data[3]  # Assuming sprint_name is the fourth item

    # Lookup the manager
    '''
    To look up the manager I need to:
    1) Identify what manager is assigned to what team.  This is solved with current def load_sprint_managers code
    2) Pass the result of def load_sprint_managers into part_sprint_data and compare each sprint to the sprint_manager[0].
        - IF the sprint_name starts with sprint_manager[0] then sprint_owner should equal the value of sprint_manager[1]
        - ELSE sprint_owner should be 'No Owner'
    '''
    #manager = managers_dict.get(sprint_name, 'No Manager')  # Default to 'No Manager' if not found
    '''
    for team in sprint_managers:
        if sprint_name starts with team:
            manager = sprint_managers[1]
    
    '''
    #return parsed_data + [manager]

def add_sprint_owner(sprint_managers, sprint_name):
    # sprint_owners = sprint_managers
    
    for team in sprint_managers:
        if sprint_name.startswith(team):
            #manager = sprint_managers[1]
            return sprint_managers[team]
    
    return 'No Manager'

def parse_sprint_data(sprint_string):
    # Load the managers dictionary
    jira_project_owner_file = '/Users/wegelpi/jira/jira-projects-owners.csv'
    sprint_managers = load_sprint_managers(jira_project_owner_file)

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

        start_index = sprint_string.find('startDate=') + len('startDate=')
        start_date = sprint_string[start_index:sprint_string.find(',', start_index)]

        end_index = sprint_string.find('endDate=') + len('endDate=')
        end_date = sprint_string[end_index:sprint_string.find(',', end_index)]

        return [state, start_date, end_date, sprint_name, sprint_owner]
    else:
        return ['No Data', 'No Data', 'No Data', 'No Data', 'No Data']  # Handle cases where format does not match

#def extract_data(string, key):
#    start_index = string.find(f'{key}=') + len(f'{key}=')
#   return string[start_index:string.find(',', start_index)]

# Load the managers dictionary
# sprint_managers = load_sprint_managers(jira_project_owner_file)
# print (sprint_managers)
# Usage
#sprint_data_string = 'your_sprint_data_string_here'  # This should come from your main data fetching function
#parsed_sprint_data = parse_sprint_data(sprint_data_string, sprint_managers)
# Example usage
# sprint_data_string should be fetched from issue.fields as before
# parsed_sprint_data = parse_sprint_data(sprint_data_string)


