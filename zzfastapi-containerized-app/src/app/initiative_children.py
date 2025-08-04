import os
import psycopg2
from jira import JIRA
from dotenv import load_dotenv
from datetime import datetime, timedelta
from dateutil.parser import parse as parse_date
import logging

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the time threshold: 6 months ago from now.
SIX_MONTHS_AGO = datetime.now() - timedelta(days=180)
# Format for JQL (e.g., "2023-04-09")
six_months_str = SIX_MONTHS_AGO.strftime("%Y-%m-%d")

def is_recent(issue):
    """
    Returns True if the issue's updated date is within the last 6 months.
    """
    try:
        updated_dt = parse_date(issue.fields.updated)
        # Convert the aware datetime to a naive datetime for comparison.
        updated_dt = updated_dt.replace(tzinfo=None)
    except Exception as e:
        logger.error(f"Error parsing updated date for issue {issue.key}: {e}")
        return False
    return updated_dt >= SIX_MONTHS_AGO


# Read allowed Jira project keys from the environment variable.
# Example: JIRA_PROJECTS=COMPDIV, COMPTRIAGE, COMPLANG, COMPUTESVCS, COMPWLM, COMPHOST, COMPDIVPUNE, GEMINI, COMPSRVCORE, COMPCONNECT, COMPOBSERVE, COMPSRVCAS
allowed_projects_str = os.getenv("JIRA_PROJECTS", "")
ALLOWED_PROJECTS = [proj.strip() for proj in allowed_projects_str.split(",") if proj.strip()]

# Initialize the Jira client.
def setup_jira_client():
    jira_api_token = os.getenv('JIRA_TOKEN')
    jira_url = os.getenv('JIRA_URL')

    jira = JIRA(
        server=jira_url,
        token_auth=jira_api_token
    )
    return jira

# Create a connection to the PostgreSQL database.
def create_connection():
    db_password = os.getenv('DB_PASSWORD')
    db_user = os.getenv('DB_USER')
    db_name = os.getenv('DB_NAME')
    db_host = os.getenv('DB_HOST')
    db_timeout = os.getenv('DB_CONN_TIMEOUT')

    conn_string = (
        f"dbname='{db_name}' user='{db_user}' password='{db_password}' "
        f"host='{db_host}' connect_timeout={db_timeout} sslmode='prefer'"
    )
    return psycopg2.connect(conn_string)

# Fetch initiative issue keys from the database.
def fetch_issue_keys():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT issue_key FROM tbl_initiative_issue_keys")
    issue_keys = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return issue_keys

# Fetch issues from Jira based on issue keys,
# but only if the issue is in an allowed project and updated in the last 6 months.
def fetch_issues(jira, issue_keys):
    all_issues = []
    for issue_key in issue_keys:
        issue = jira.issue(
            issue_key,
            fields="key,summary,issuetype,status,assignee,created,updated,issuelinks,parent,subtasks,customfield_10002,project"
        )
        if issue.fields.project.key not in ALLOWED_PROJECTS:
            logger.info(f"Issue {issue.key} not in allowed projects, skipping.")
            continue
        if not is_recent(issue):
            logger.info(f"Issue {issue.key} was not updated in the last 6 months, skipping.")
            continue

        all_issues.append((issue_key, issue))
        # Fetch related issues recursively.
        related_issues = fetch_related_issues(jira, issue, initiative_issue_key=issue_key)
        all_issues.extend(related_issues)
    return all_issues

# Maximum recursion depth safeguard.
MAX_RECURSION_DEPTH = 10

# Fetch related issues (both direct and indirect) recursively.
def fetch_related_issues(jira, issue, visited=None, depth=0, initiative_issue_key=None):
    if visited is None:
        visited = set()
    
    if depth > MAX_RECURSION_DEPTH:
        logger.warning(f"Maximum recursion depth of {MAX_RECURSION_DEPTH} reached for issue {issue.key}")
        return []

    related_issues = []
    issue_links = getattr(issue.fields, "issuelinks", [])
    
    # Allowed link types now include several relationship variants.
    allowed_link_types = [
        "Is Child", "Is Parent", "Relates", "Is Related To", "Related", "Has Parent", "Hierarchy"
    ]

    for link in issue_links:
        inward = getattr(link, "inwardIssue", None)
        outward = getattr(link, "outwardIssue", None)
        link_type = getattr(link, "type", None)
        
        if link_type:
            logger.info(f"Issue {issue.key} has link type: {link_type.name}")
        else:
            logger.info(f"Issue {issue.key} has a link with no defined type.")

        if link_type and link_type.name in allowed_link_types:
            if inward and inward.key not in visited:
                visited.add(inward.key)
                logger.info(f"Fetching inward issue: {inward.key}")
                related_issue = jira.issue(
                    inward.key,
                    fields="key,summary,issuetype,status,assignee,created,updated,issuelinks,parent,subtasks,customfield_10002,project"
                )
                if related_issue.fields.project.key in ALLOWED_PROJECTS and is_recent(related_issue):
                    related_issues.append((initiative_issue_key, related_issue))
                    related_issues.extend(fetch_related_issues(jira, related_issue, visited, depth + 1, initiative_issue_key))
                else:
                    logger.info(f"Issue {related_issue.key} not in allowed projects or not updated recently, skipping.")
            if outward and outward.key not in visited:
                visited.add(outward.key)
                logger.info(f"Fetching outward issue: {outward.key}")
                related_issue = jira.issue(
                    outward.key,
                    fields="key,summary,issuetype,status,assignee,created,updated,issuelinks,parent,subtasks,customfield_10002,project"
                )
                if related_issue.fields.project.key in ALLOWED_PROJECTS and is_recent(related_issue):
                    related_issues.append((initiative_issue_key, related_issue))
                    related_issues.extend(fetch_related_issues(jira, related_issue, visited, depth + 1, initiative_issue_key))
                else:
                    logger.info(f"Issue {related_issue.key} not in allowed projects or not updated recently, skipping.")

    # If the issue is an Epic, fetch its children using a JQL query that only returns recently updated child issues.
    if issue.fields.issuetype.name == "Epic":
        jql = f'"Epic Link" = "{issue.key}" AND updated >= "{six_months_str}"'
        logger.info(f"Querying Epic children with JQL: {jql}")
        epic_children = jira.search_issues(
            jql,
            fields="key,summary,issuetype,status,assignee,created,updated,issuelinks,parent,subtasks,customfield_10002,project"
        )
        for child in epic_children:
            if child.key not in visited:
                visited.add(child.key)
                if child.fields.project.key in ALLOWED_PROJECTS and is_recent(child):
                    related_issues.append((initiative_issue_key, child))
                    related_issues.extend(fetch_related_issues(jira, child, visited, depth + 1, initiative_issue_key))
                else:
                    logger.info(f"Epic child {child.key} not in allowed projects or not updated recently, skipping.")
    return related_issues

# Store issues in PostgreSQL.
def store_issues(issues):
    conn = create_connection()
    cursor = conn.cursor()
    for initiative_issue_key, issue in issues:
        issue_key = issue.key
        summary = issue.fields.summary
        issue_type = issue.fields.issuetype.name
        status = issue.fields.status.name
        assignee = issue.fields.assignee.displayName if issue.fields.assignee else 'Unassigned'
        created = issue.fields.created
        updated = issue.fields.updated
        story_points = getattr(issue.fields, 'customfield_10002', None)
        effective_dttm = datetime.now()

        if story_points is None:
            story_points = 0

        cursor.execute("""
            INSERT INTO tbl_initiative_children (
                initiative_issue_key, issue_key, summary, issue_type, status, assignee, created, updated, story_points, effective_dttm
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (initiative_issue_key, issue_key, summary, issue_type, status, assignee, created, updated, story_points, effective_dttm))

    conn.commit()
    cursor.close()
    conn.close()

# Main function.
def init_child_main():
    jira = setup_jira_client()
    issue_keys = fetch_issue_keys()
    issues = fetch_issues(jira, issue_keys)
    store_issues(issues)

if __name__ == "__main__":
    init_child_main()
