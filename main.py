from jira import JIRA
import csv
from datetime import datetime
# Your server URL 
options = {'server': 'https://rndjira.sas.com/'}

# Connect to JIRA
file_path = '/Users/wegelpi/encrypt/secrets/jira-token.txt'

with open(file_path, 'r') as file:
    jira_api_token = file.read().strip()

jira_email = 'wes.gelpi@sas.com'

try:
    
    ## Initialize the JIRA client without authentication
    jira = JIRA(options=options)

    ## Set the Authorization header on the session object directly
    jira._session.headers.update({'Authorization': f'Bearer {jira_api_token}'})

    # Retrieve all open issues from the COMPUTESVCS project
    jql_query = 'project = COMPUTESVCS AND resolution = Unresolved'
    issues = jira.search_issues(jql_query, maxResults=2000)  # Adjust maxResults as needed

    # Generate a timestamp for the filename
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

    # Define the filename and the fields to export
    csv_file = f'/Users/wegelpi/Downloads/jira-output-{timestamp}.csv'
    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['Issue Key', 'Summary', 'Type', 'Assignee', 'Status'])  # Customize headers as needed

        for issue in issues:
            # Extract the fields you need from each issue
            assignee = issue.fields.assignee.displayName if issue.fields.assignee else 'Unassigned'
            status = issue.fields.status.name if issue.fields.status else 'No Status'
            type = issue.fields.issuetype if issue.fields.issuetype else 'No Type'
            #date = issue.fields.timetracking if issue.fields.timetracking else 'No timetracking'
            writer.writerow([issue.key, issue.fields.summary, type, assignee, status])

    print("Issues exported successfully to CSV.")


except Exception as e:
    print(f"Failed to authenticate: {e}")
    if hasattr(e, 'response'):
        print("Status code:", e.response.status_code)
        print("Error response:", e.response.text)

