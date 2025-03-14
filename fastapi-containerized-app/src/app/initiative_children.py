import os
import psycopg2
from jira import JIRA
from dotenv import load_dotenv
from datetime import datetime
import logging

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Initialize the Jira client
def setup_jira_client():
    jira_api_token = os.getenv('JIRA_TOKEN')
    jira_url = os.getenv('JIRA_URL')

    jira = JIRA(
        server=jira_url,
        token_auth=jira_api_token
    )

    # Removed direct update of _session.headers
    return jira

# Create a connection to the PostgreSQL database
def create_connection():
    db_password = os.getenv('DB_PASSWORD')
    db_user = os.getenv('DB_USER')
    db_name = os.getenv('DB_NAME')
    db_host = os.getenv('DB_HOST')
    db_timeout = os.getenv('DB_CONN_TIMEOUT')

    conn_string = f"dbname='{db_name}' user='{db_user}' password='{db_password}' host='{db_host}' connect_timeout={db_timeout} sslmode='prefer'"
    return psycopg2.connect(conn_string)

# Fetch issue keys from the database
def fetch_issue_keys():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT issue_key FROM tbl_initiative_issue_keys")
    issue_keys = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return issue_keys

# Fetch issues from Jira based on issue keys
def fetch_issues(jira, issue_keys):
    all_issues = []
    for issue_key in issue_keys:
        issue = jira.issue(issue_key, fields="issue.key,summary,issuetype,status,assignee,created,updated,issuelinks,parent,subtasks,customfield_10002")
        all_issues.append((issue_key, issue))  # Store the initiative_issue_key with the issue
        # Fetch related issues
        related_issues = fetch_related_issues(jira, issue, initiative_issue_key=issue_key)
        all_issues.extend(related_issues)
    return all_issues

# Fetch related issues (both direct and indirect)
MAX_RECURSION_DEPTH = 750
'''This does not appear to be filtering on just the initiative jiras before running the recursion.
One example of this:'''
def fetch_related_issues(jira, issue, visited=None, depth=0, initiative_issue_key=None):
    if visited is None:
        visited = set()
    
    if depth > MAX_RECURSION_DEPTH:
        logger.warning(f"Maximum recursion depth of {MAX_RECURSION_DEPTH} reached for issue {issue.key}")
        return []

    related_issues = []
    issue_links = getattr(issue.fields, "issuelinks", [])
    for link in issue_links:
        inward = getattr(link, "inwardIssue", None)
        outward = getattr(link, "outwardIssue", None)
        link_type = getattr(link, "type", None)

        if link_type and link_type.name in ["Is Child", "Is Parent", "Relates"]:
            if inward and inward.key not in visited:
                visited.add(inward.key)
                print(f"Fetching inward.key: {inward.key}")
                related_issue = jira.issue(inward.key, fields="issue.key,summary,issuetype,status,assignee,created,updated,issuelinks,parent,subtasks,customfield_10002")
                related_issues.append((initiative_issue_key, related_issue))  # Store the initiative_issue_key with the related issue
                related_issues.extend(fetch_related_issues(jira, related_issue, visited, depth + 1, initiative_issue_key))
            if outward and outward.key not in visited:
                visited.add(outward.key)
                print(f"Fetching outward.key {outward.key}")
                related_issue = jira.issue(outward.key, fields="issue.key,summary,issuetype,status,assignee,created,updated,issuelinks,parent,subtasks,customfield_10002")
                related_issues.append((initiative_issue_key, related_issue))  # Store the initiative_issue_key with the related issue
                related_issues.extend(fetch_related_issues(jira, related_issue, visited, depth + 1, initiative_issue_key))

    # Check if the issue is an Epic and fetch its children
    if issue.fields.issuetype.name == "Epic":
        jql = f'"Epic Link" = {issue.key}'
        epic_children = jira.search_issues(jql, fields="issue.key,summary,issuetype,status,assignee,created,updated,issuelinks,parent,subtasks,customfield_10002")
        for child in epic_children:
            if child.key not in visited:
                visited.add(child.key)
                related_issues.append((initiative_issue_key, child))  # Store the initiative_issue_key with the child issue
                related_issues.extend(fetch_related_issues(jira, child, visited, depth + 1, initiative_issue_key))

    return related_issues

# Store issues in PostgreSQL
def store_issues(issues):
    conn = create_connection()
    cursor = conn.cursor()
    for initiative_issue_key, issue in issues:
        issue_key = issue.key
        print(f"Storing issue {issue_key}")
        summary = issue.fields.summary
        issue_type = issue.fields.issuetype.name
        print(f"Issue type {issue_type}")
        status = issue.fields.status.name
        print(f"Status {status}")
        assignee = issue.fields.assignee.displayName if issue.fields.assignee else 'Unassigned'
        print(f"Assignee {assignee}")
        created = issue.fields.created
        print(f"Created {created}")
        updated = issue.fields.updated
        story_points = getattr(issue.fields, 'customfield_10002', None)
        print(f"Story points {story_points}")

        if story_points is None:
            story_points = 0
        # insert_sql = ""
        cursor.execute("""
            INSERT INTO tbl_initiative_children (initiative_issue_key, issue_key, summary, issue_type, status, assignee, created, updated, story_points)
            VALUES (%s,%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (issue_key) DO UPDATE
            SET initiative_issue_key = EXCLUDED.initiative_issue_key,
                issue_key = EXCLUDED.issue_key,
                summary = EXCLUDED.summary,
                issue_type = EXCLUDED.issue_type,
                status = EXCLUDED.status,
                assignee = EXCLUDED.assignee,
                created = EXCLUDED.created,
                updated = EXCLUDED.updated
        """, (initiative_issue_key, issue_key, summary, issue_type, status, assignee, created, updated, story_points))
    conn.commit()
    cursor.close()
    conn.close()

# Main function
def main():
    jira = setup_jira_client()
    issue_keys = fetch_issue_keys()
    issues = fetch_issues(jira, issue_keys)
    store_issues(issues)

if __name__ == "__main__":
    main()