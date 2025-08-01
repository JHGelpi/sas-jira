import os
import logging
from datetime import datetime, timedelta
from dateutil.parser import parse as parse_date
from jira import JIRA
import psycopg2.extras

# Use relative imports
from . import db_utils

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

def fetch_issues_in_batch(jira, keys: set, chunk_size: int = 100) -> dict:
    """
    Fetches a set of issues from Jira using batched JQL queries to avoid URL length limits.
    """
    if not keys:
        return {}
    
    all_results = {}
    key_list = list(keys) # Convert set to list for slicing

    logger.info(f"Batch fetching {len(key_list)} issues in chunks of {chunk_size}...")

    for i in range(0, len(key_list), chunk_size):
        chunk = key_list[i:i + chunk_size]
        jql = f"key in ({','.join(f'\"{k}\"' for k in chunk)})"
        
        try:
            # Request all necessary fields at once
            results = jira.search_issues(
                jql,
                maxResults=len(chunk),
                fields="key,summary,issuetype,status,assignee,created,updated,issuelinks,parent,subtasks,project,customfield_10002"
            )
            for issue in results:
                all_results[issue.key] = issue
            logger.info(f"-> Fetched chunk {i//chunk_size + 1}, found {len(results)} issues.")
        except Exception as e:
            logger.error(f"Failed to fetch a chunk of issues with JQL: {jql}. Error: {e}")
            # Continue to the next chunk
            continue
            
    return all_results

def store_issues_bulk(db_pool, issues_to_store: dict):
    """
    Stores a dictionary of issues in the database by separating inserts and updates.
    This avoids using ON CONFLICT, which requires a unique constraint.
    """
    if not issues_to_store:
        logger.info("No new issues to store.")
        return

    conn = db_pool.getconn()
    try:
        with conn.cursor() as cursor:
            # 1. Fetch all existing issue keys from the target table
            logger.info("Fetching existing issue keys from tbl_initiative_children...")
            cursor.execute("SELECT issue_key FROM tbl_initiative_children")
            existing_keys = {row[0] for row in cursor.fetchall()}
            logger.info(f"Found {len(existing_keys)} existing keys.")

            # 2. Separate issues into two lists: one for new inserts, one for updates
            rows_to_insert = []
            rows_to_update = []

            for initiative_key, issue in issues_to_store.values():
                story_points = getattr(issue.fields, 'customfield_10002', 0) or 0
                assignee = issue.fields.assignee.displayName if issue.fields.assignee else 'Unassigned'
                
                # The order of columns here must match the INSERT and UPDATE statements
                data_tuple = (
                    initiative_key, issue.key, issue.fields.summary, issue.fields.issuetype.name,
                    issue.fields.status.name, assignee, issue.fields.created, issue.fields.updated,
                    float(story_points), datetime.now()
                )

                if issue.key in existing_keys:
                    rows_to_update.append(data_tuple)
                else:
                    rows_to_insert.append(data_tuple)
            
            # 3. Perform bulk INSERT for new rows
            if rows_to_insert:
                logger.info(f"Inserting {len(rows_to_insert)} new records...")
                insert_query = """
                    INSERT INTO tbl_initiative_children (
                        initiative_issue_key, issue_key, summary, issue_type, status, assignee, 
                        created, updated, story_points, effective_dttm
                    ) VALUES %s
                """
                psycopg2.extras.execute_values(cursor, insert_query, rows_to_insert)
                logger.info("Bulk insert complete.")

            # 4. Perform bulk UPDATE for existing rows
            if rows_to_update:
                logger.info(f"Updating {len(rows_to_update)} existing records...")
                # Note: This will update ALL rows that match a given issue_key.
                # This is necessary given the database design where issue_key is not unique.
                update_query = """
                    UPDATE tbl_initiative_children AS t SET
                        initiative_issue_key = v.initiative_issue_key,
                        summary = v.summary,
                        issue_type = v.issue_type,
                        status = v.status,
                        assignee = v.assignee,
                        created = v.created,
                        updated = v.updated,
                        story_points = v.story_points,
                        effective_dttm = v.effective_dttm
                    FROM (VALUES %s) AS v(
                        initiative_issue_key, issue_key, summary, issue_type, status, assignee, 
                        created, updated, story_points, effective_dttm
                    )
                    WHERE t.issue_key = v.issue_key;
                """
                psycopg2.extras.execute_values(cursor, update_query, rows_to_update)
                logger.info("Bulk update complete.")

            conn.commit()
            
    except Exception as e:
        conn.rollback()
        logger.error(f"Database bulk operation failed: {e}")
    finally:
        db_pool.putconn(conn)

def main():
    """Main function to fetch and store initiative-related issues."""
    jira = get_jira_client()
    db_pool = db_utils.get_connection_pool()
    
    allowed_projects_str = os.getenv("JIRA_PROJECTS", "")
    allowed_projects = {proj.strip() for proj in allowed_projects_str.split(',') if proj.strip()}
    
    initial_keys = db_utils.fetch_initiative_keys(db_pool)
    if not initial_keys:
        logger.warning("No initial initiative keys found in the database.")
        return
        
    all_related_issues = {} 
    visited_keys = set()
    keys_to_fetch = set(initial_keys)
    
    depth = 0
    while keys_to_fetch and depth <= MAX_RECURSION_DEPTH:
        logger.info(f"Recursion Depth: {depth}. Keys to fetch: {len(keys_to_fetch)}.")
        
        fetched_issues_map = fetch_issues_in_batch(jira, keys_to_fetch)
        visited_keys.update(keys_to_fetch)
        
        next_keys = set() 

        for key, issue in fetched_issues_map.items():
            initiative_key = key if key in initial_keys else next((ik for ik, i_obj in all_related_issues.values() if i_obj.key == key), None)
            
            if not is_issue_valid(issue, allowed_projects):
                continue

            if key not in all_related_issues:
                all_related_issues[key] = (initiative_key, issue)

            for link in getattr(issue.fields, "issuelinks", []):
                if getattr(link, 'type', None) and link.type.name in ALLOWED_LINK_TYPES:
                    linked_issue_obj = getattr(link, "inwardIssue", None) or getattr(link, "outwardIssue", None)
                    if linked_issue_obj and linked_issue_obj.key not in visited_keys:
                        next_keys.add(linked_issue_obj.key)
            
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
