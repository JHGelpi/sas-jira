#from jira import JIRA
#import csv
from datetime import datetime

def parse_sprint_data(sprint_string):
    # Handle None input early
    if sprint_string is None:
        return ['No Data', 'No Data', 'No Data', 'No Data']

    # Ensure the sprint_string is a string and not empty
    if isinstance(sprint_string, list) and sprint_string:
        sprint_string = sprint_string[0]
    elif not isinstance(sprint_string, str) or not sprint_string:
        return ['No Data', 'No Data', 'No Data', 'No Data']

    # Trim whitespace which might affect substring search
    sprint_string = sprint_string.strip()

    # Check for the presence of the desired pattern
    if 'state=' in sprint_string and 'startDate=' in sprint_string and 'endDate=' in sprint_string:
        # Extract the information
        state_index = sprint_string.find('state=') + len('state=')
        state = sprint_string[state_index:sprint_string.find(',', state_index)]

        sprint_name_index = sprint_string.find('name=') + len('name=')
        sprint_name = sprint_string[sprint_name_index:sprint_string.find(',', sprint_name_index)]

        start_index = sprint_string.find('startDate=') + len('startDate=')
        start_date = sprint_string[start_index:sprint_string.find(',', start_index)]

        end_index = sprint_string.find('endDate=') + len('endDate=')
        end_date = sprint_string[end_index:sprint_string.find(',', end_index)]

        return [state, start_date, end_date, sprint_name]
    else:
        return ['No Data', 'No Data', 'No Data', 'No Data']  # Handle cases where format does not match

# Example usage
# sprint_data_string should be fetched from issue.fields as before
# parsed_sprint_data = parse_sprint_data(sprint_data_string)


