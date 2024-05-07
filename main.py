from jira import JIRA

# Your server URL 
options = {'server': 'https://rndjira.sas.com/projects/COMPUTESVCS/'}

# Connect to JIRA
file_path = '/Users/wegelpi/encrypt/secrets/jira-token.txt'

with open(file_path, 'r') as file:
    jira_api_token = file.read().strip()

jira_email = 'wes.gelpi@sas.com'

try:
    jira = JIRA(options, basic_auth=(jira_email, jira_api_token))
    print("Authentication successful")
except Exception as e:
    print(f"Failed to authenticate: {e}")
    if hasattr(e, 'response'):
        print("Status code:", e.response.status_code)
        print("Error response:", e.response.text)
# jira = JIRA(options, basic_auth=(jira_email, jira_api_token))

# Example of fetching an issue
# issue = jira.issue('COMPUTESVCS-61066')
# print(issue.fields.summary)  # Prints the summary of the issue

