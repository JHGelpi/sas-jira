from jira import JIRA
import csv
from datetime import datetime
from sprint_parser import parse_sprint_data
# Your server URL 
options = {'server': 'https://rndjira.sas.com/'}

start_date = datetime.now()
formatted_start_date = start_date.strftime('%d-%m-%y %H:%M:%S')
print("Starting at....", formatted_start_date)

# Connect to JIRA
file_path = '/Users/wegelpi/encrypt/secrets/jira-token.txt'

with open(file_path, 'r') as file:
    jira_api_token = file.read().strip()

#jira_email = 'wes.gelpi@sas.com'

#try:
    
## Initialize the JIRA client without authentication
jira = JIRA(options=options)

## Set the Authorization header on the session object directly
jira._session.headers.update({'Authorization': f'Bearer {jira_api_token}'})

# Retrieve all open issues from the COMPUTESVCS project
#jql_query = 'project = COMPUTESVCS AND resolution = Unresolved'
jql_query = 'project = "Compute Services" AND resolution = Unresolved AND Sprint is not EMPTY'
#issues = jira.search_issues(jql_query, maxResults=2000)  # Adjust maxResults as needed

# Initialize pagination
start_at = 0
max_results = 750  # Use smaller batches for safer memory management
all_issues = []

while True:
    issues = jira.search_issues(jql_query, startAt=start_at, maxResults=max_results)
    all_issues.extend(issues)
    if len(issues) < max_results:
        break
    start_at += len(issues)

# Now `all_issues` contains all issues that match the query
print(f"Total issues retrieved: {len(all_issues)}")

# Generate a timestamp for the filename
timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

# Define the filename and the fields to export
csv_file = f'/Users/wegelpi/jira/jira-output-{timestamp}.csv'
with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    writer.writerow(['Issue Key', 'Summary', 'Type', 'State', 'Assignee', 'Status', 'Start Date', 'End Date', 'Sprint Name'])  # Customize headers as needed

    for issue in all_issues:
        # Extract the fields you need from each issue
        assignee = issue.fields.assignee.displayName if issue.fields.assignee else 'Unassigned'
        status = issue.fields.status.name if issue.fields.status else 'No Status'
        type = issue.fields.issuetype if issue.fields.issuetype else 'No Type'
        sprint_data_string = getattr(issue.fields, 'customfield_10102', 'No Data')
        parsed_sprint_data = parse_sprint_data(sprint_data_string)
        writer.writerow([issue.key, issue.fields.summary, type, parsed_sprint_data[0], assignee, status, parsed_sprint_data[1], parsed_sprint_data[2], parsed_sprint_data[3]])

start_date = datetime.now()
formatted_start_date = start_date.strftime('%d-%m-%y %H:%M:%S')

print(f"Issues exported successfully to CSV.{formatted_start_date}")