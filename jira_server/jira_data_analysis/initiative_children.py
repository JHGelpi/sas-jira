import os
import logging
from datetime import datetime, timedelta
from dateutil.parser import parse as parse_date
from jira import JIRA
import psycopg2.extras

import db_utils # Use the centralized DB utilities

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
MAX_RECURSION_DEPTH = 10
SIX_MONTHS_AGO = datetime.now().utcnow().replace(tzinfo=None) - timedelta(days=180)
ALLOWED_LINK_TYPES = {"Is Child", "Is Parent", "Relates", "Is Related To", "Related", "Has Parent", "Hierarchy"}

def get_jira_client():
    """Initializes and returns a JIRA client."""
    return JIRA(server=os.getenv('JIRA_URL'), token_auth=os.getenv('JIRA_TOKEN'))

def is_issue_valid(issue, allowed_projects_set: set) -> bool:
    """Checks if an issue is in an allowed project and was updated recently."""
    if issue.fields.project.key not in allowed_projects_set:
        return False
    try:
        updated_dt = parse_date(issue.fields.updated).replace(tzinfo=None)
        if updated_dt < SIX_MONTHS_AGO:
            return False
    except (TypeError, ValueError):
        return False # Invalid date format
    return True

def fetch_issues_in_batch(jira, keys: set) -> dict:
    """Fetches a set of issues from Jira using a single batched JQL query."""
    if not keys:
        return {}
    
    # JQL is more efficient for batch fetching
    jql = f"key in ({','.join(f'\"{k}\"' for k in keys)})"
    logger.info(f"Batch fetching {len(keys)} issues from Jira...")
    
    try:
        # Request all necessary fields at once
        results = jira.search_issues(
            jql,
            maxResults=len(keys),
            fields="key,summary,issuetype,status,assignee,created,updated,issuelinks,parent,subtasks,project,customfield_10002"
        )
        return {issue.key: issue for issue in results}
    except Exception as e:
        logger.error(f"Failed to batch fetch issues: {e}")
        return {}

def store_issues_bulk(db_pool, issues_to_store: dict):
    """Stores a dictionary of issues in the database using a bulk insert."""
    if not issues_to_store:
        logger.info("No new issues to store.")
        return

    conn = db_pool.getconn()
    try:
        with conn.cursor() as cursor:
            insert_data = []
            for initiative_key, issue in issues_to_store.values():
                story_points = getattr(issue.fields, 'customfield_10002', 0) or 0
                assignee = issue.fields.assignee.displayName if issue.fields.assignee else 'Unassigned'
                
                insert_data.append((
                    initiative_key, issue.key, issue.fields.summary, issue.fields.issuetype.name,
                    issue.fields.status.name, assignee, issue.fields.created, issue.fields.updated,
                    float(story_points), datetime.now()
                ))
            
            # Use execute_values for efficient bulk insertion
            psycopg2.extras.execute_values(
                cursor,
                """
                INSERT INTO tbl_initiative_children (
                    initiative_issue_key, issue_key, summary, issue_type, status, assignee, 
                    created, updated, story_points, effective_dttm
                ) VALUES %s
                ON CONFLICT (issue_key) DO UPDATE SET
                    initiative_issue_key = EXCLUDED.initiative_issue_key,
                    summary = EXCLUDED.summary,
                    status = EXCLUDED.status,
                    updated = EXCLUDED.updated,
                    story_points = EXCLUDED.story_points,
                    effective_dttm = EXCLUDED.effective_dttm;
                """,
                insert_data
            )
            conn.commit()
            logger.info(f"Successfully inserted/updated {len(insert_data)} records.")
            
    except Exception as e:
        conn.rollback()
        logger.error(f"Database bulk insert failed: {e}")
    finally:
        db_pool.putconn(conn)

def main():
    """Main function to fetch and store initiative-related issues."""
    jira = get_jira_client()
    db_pool = db_utils.get_connection_pool()
    
    # Load configuration from environment
    allowed_projects_str = os.getenv("JIRA_PROJECTS", "")
    allowed_projects = {proj.strip() for proj in allowed_projects_str.split(',') if proj.strip()}
    
    initial_keys = db_utils.fetch_initiative_keys(db_pool)
    if not initial_keys:
        logger.warning("No initial initiative keys found in the database.")
        return
        
    all_related_issues = {} # Stores {child_key: (initiative_key, issue_object)}
    visited_keys = set()
    keys_to_fetch = set(initial_keys)
    
    depth = 0
    while keys_to_fetch and depth <= MAX_RECURSION_DEPTH:
        logger.info(f"Recursion Depth: {depth}. Fetching {len(keys_to_fetch)} keys.")
        
        # Fetch the current batch of issues
        fetched_issues_map = fetch_issues_in_batch(jira, keys_to_fetch)
        visited_keys.update(keys_to_fetch)
        
        next_keys = set() # Keys to fetch in the next iteration

        for key, issue in fetched_issues_map.items():
            # Determine the root initiative for this issue
            # If the key is an initial one, it's its own initiative.
            # Otherwise, it inherits from the issue that linked to it.
            initiative_key = key if key in initial_keys else next((ik for ik, i_obj in all_related_issues.values() if i_obj.key == key), None)
            
            if not is_issue_valid(issue, allowed_projects):
                continue

            # Add the valid issue to our collection
            if key not in all_related_issues:
                all_related_issues[key] = (initiative_key, issue)

            # 1. Gather keys from issue links
            for link in getattr(issue.fields, "issuelinks", []):
                if getattr(link, 'type', None) and link.type.name in ALLOWED_LINK_TYPES:
                    linked_issue_obj = getattr(link, "inwardIssue", None) or getattr(link, "outwardIssue", None)
                    if linked_issue_obj and linked_issue_obj.key not in visited_keys:
                        next_keys.add(linked_issue_obj.key)
            
            # 2. If it's an Epic, gather its children via JQL
            if issue.fields.issuetype.name == "Epic":
                six_months_str = SIX_MONTHS_AGO.strftime("%Y-%m-%d")
                jql = f'"Epic Link" = "{issue.key}" AND updated >= "{six_months_str}"'
                try:
                    epic_children = jira.search_issues(jql, fields="key")
                    for child in epic_children:
                        if child.key not in visited_keys:
                            next_keys.add(child.key)
                except Exception as e:
                    logger.error(f"Failed to fetch children for Epic {issue.key}: {e}")

        keys_to_fetch = next_keys
        depth += 1
        
    if depth > MAX_RECURSION_DEPTH:
        logger.warning(f"Reached max recursion depth of {MAX_RECURSION_DEPTH}.")
        
    store_issues_bulk(db_pool, all_related_issues)

if __name__ == "__main__":
    main()