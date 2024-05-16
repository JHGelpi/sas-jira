from jira import JIRA
import csv
from datetime import datetime
from sprint_parser import parse_sprint_data, add_oper_epic, triage_parser, oper_parser, escaped_bug_flag, format_date
from jql_builder import build_jql_completed, build_jql_active
from export_to_postgres import append_csv
from component_parser import parse_component_data, parse_fix_version_data, parse_label_data
#from fix_version_parser import parse_fix_version_data
# Server URL 
options = {'server': 'https://rndjira.sas.com/'}

start_date = datetime.now()
formatted_start_date = start_date.strftime('%d-%m-%y %H:%M:%S')
print("Starting at....", formatted_start_date)

# Connect to JIRA
file_path = '/Users/wegelpi/encrypt/secrets/jira-token.txt'

with open(file_path, 'r') as file:
    jira_api_token = file.read().strip()

#try:
    
## Initialize the JIRA client without authentication
jira = JIRA(options=options)

## Set the Authorization header on the session object directly
jira._session.headers.update({'Authorization': f'Bearer {jira_api_token}'})

# Retrieve all open issues from the COMPUTESVCS and GEMINI project
#jql_query = build_jql_active()
jql_query = build_jql_completed('2024.04')

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

# `all_issues` contains all issues that match the query
print(f"Total issues retrieved: {len(all_issues)}")

# Generate a timestamp for the filename
timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

# Define the filename and the fields to export
csv_file = f'/Users/wegelpi/jira/jira-output-{timestamp}.csv'
with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
    #writer = csv.writer(file)
    writer = csv.writer(file, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)  # Ensure all fields are quoted
    writer.writerow(['Epic Link', 'Parent Link','Operational Epic Team', 'Operational Flag', 'Triage Origin', 'Pipeline Discovery Stage','Bug Origin', 'Escaped Bug', 'Fix Version', 'Component','Issue Key', 'Summary', 'Issue URL', 'Type', 'State', 'Assignee', 'Status', 'Start Date', 'End Date', 'Sprint Name', 'Labels', 'Sprint Owner', 'Export Date'])

    for issue in all_issues:
        # Extract the fields you need from each issue
        assignee = issue.fields.assignee.displayName if issue.fields.assignee else 'Unassigned'
        status = issue.fields.status.name if issue.fields.status else 'No Status'
        type = issue.fields.issuetype if issue.fields.issuetype else 'No Type'
        sprint_data_string = getattr(issue.fields, 'customfield_10102', 'No Data')
        parsed_sprint_data = parse_sprint_data(sprint_data_string)
        sprint_start_date = format_date(parsed_sprint_data[1])
        sprint_end_date = format_date(parsed_sprint_data[2])
        issue_url = 'https://rndjira.sas.com/browse/' + str(issue.key)
        epic_link = getattr(issue.fields, 'customfield_10301', '')
        parent_link = getattr(issue.fields, 'customfield_16301', 'No Parent')
        oper_epic = add_oper_epic(epic_link)
        #labels = getattr(issue.fields, 'labels', '')
        labels = parse_label_data(getattr(issue.fields, 'labels', ''))
        pipeline_stage = str(getattr(issue.fields, 'customfield_15600', ''))
        bug_origin = str(getattr(issue.fields, 'customfield_14504', ''))
        escaped_bug = 'Y' if escaped_bug_flag(bug_origin, pipeline_stage) else 'N'
        triage_flg = 'Y' if triage_parser(labels) else 'N'
        oper_flg = 'Y' if oper_parser(labels) else 'N'
        fix_version = parse_fix_version_data(getattr(issue.fields, 'fixVersions', ''))
        export_date = start_date.strftime('%Y-%m-%d %H:%M:%S')
        #fix_version = getattr(issue.fields, 'fixVersions', '')
        #components = getattr(issue.fields, 'components', '')
        #components_string = getattr(issue.fields, 'components', '')
        components = parse_component_data(getattr(issue.fields, 'components', ''))

        writer.writerow([epic_link, parent_link,oper_epic, oper_flg, triage_flg, pipeline_stage, bug_origin, escaped_bug, fix_version, components, issue.key, issue.fields.summary, issue_url, type, parsed_sprint_data[0], assignee, status, sprint_start_date, sprint_end_date, parsed_sprint_data[3], labels, parsed_sprint_data[4], export_date])

append_csv(csv_file)
start_date = datetime.now()
formatted_start_date = start_date.strftime('%d-%m-%y %H:%M:%S')

print(f"Issues exported successfully to CSV.{formatted_start_date}")