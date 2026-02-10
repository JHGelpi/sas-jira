# jira_data_analysis/initiative_children.py
"""
Initiative hierarchy analysis.

This module fetches initiatives from JQL, recursively discovers all related issues
(via links and epic relationships), and stores them in the database.
"""

import os
from datetime import datetime, timedelta
from dateutil.parser import parse as parse_date
from jira import JIRA
import psycopg2.extras
import traceback

from jira_data_analysis import db_utils
from logging_utils import get_logger, log_section_header

logger = get_logger(__name__)

# Constants
MAX_RECURSION_DEPTH = 10
SIX_MONTHS_AGO = datetime.now().utcnow().replace(tzinfo=None) - timedelta(days=180)
ALLOWED_LINK_TYPES = {"Is Child", "Is Parent", "Relates", "Is Related To", "Related", "Has Parent", "Hierarchy"}


def get_jira_client():
    """Initializes and returns a JIRA client."""
    logger.connecting("Connecting to Jira")
    try:
        jira = JIRA(server=os.getenv('JIRA_URL'), token_auth=os.getenv('JIRA_TOKEN'))
        logger.success("Connected to Jira")
        return jira
    except Exception as e:
        logger.error(f"Failed to connect to Jira: {e}")
        return None


def close_completed_initiatives(jira, db_pool, initiative_type=None):
    """
    Checks active initiatives and closes them if they are in a closed statusCategory.
    Sets eff_end_date to current date and active_flag to false for closed initiatives.

    *** DATA SAFETY ***
    This function ONLY updates tbl_initiative_issue_keys metadata.
    It NEVER modifies burndown data tables.
    All changes are reversible via SQL UPDATE commands.

    Args:
        jira: Jira client instance
        db_pool: Database connection pool
        initiative_type: Filter for which initiatives to check:
            - 'IRIS': Only IRIS initiatives (where "IRIS" = true)
            - 'ORCHDEPT': Only ORCHDEPT initiatives (where issue_key ~ '^ORCHDEPT-\\d+$')
            - None: All initiatives regardless of type

    Returns:
        List of epic keys that were closed
    """
    type_label = initiative_type or "ALL"
    log_section_header(logger, f"CLOSE COMPLETED {type_label} INITIATIVES")

    conn = db_pool.getconn()
    try:
        # Build query based on initiative type
        with conn.cursor() as cursor:
            if initiative_type == 'IRIS':
                query = """
                    SELECT issue_key
                    FROM tbl_initiative_issue_keys
                    WHERE "IRIS" = true
                      AND (active_flag IS NULL OR active_flag = true)
                """
                params = []
            elif initiative_type == 'ORCHDEPT':
                query = """
                    SELECT issue_key
                    FROM tbl_initiative_issue_keys
                    WHERE issue_key ~ '^ORCHDEPT-\\d+$'
                      AND (active_flag IS NULL OR active_flag = true)
                """
                params = []
            else:
                # All initiatives
                query = """
                    SELECT issue_key
                    FROM tbl_initiative_issue_keys
                    WHERE (active_flag IS NULL OR active_flag = true)
                """
                params = []

            cursor.execute(query, params)
            active_keys = [row[0] for row in cursor.fetchall()]

        if not active_keys:
            logger.info(f"No active {type_label} initiatives found in database")
            return []

        logger.info(f"Found {len(active_keys)} active {type_label} initiatives to check")

        # Fetch status information from Jira for all active initiatives
        keys_to_close = []

        for i in range(0, len(active_keys), 100):
            chunk = active_keys[i:i + 100]
            jql = f"key in ({','.join(f'\"{k}\"' for k in chunk)})"

            try:
                logger.searching(f"Checking status for batch {i//100 + 1} ({len(chunk)} issues)")
                issues = jira.search_issues(jql, fields="key,status", maxResults=len(chunk))

                for issue in issues:
                    status_category = issue.fields.status.statusCategory.name
                    logger.debug(f"{issue.key}: statusCategory = {status_category}")

                    if status_category.lower() == "done":
                        logger.info(f"{issue.key} is in closed statusCategory '{status_category}' - marking for closure")
                        keys_to_close.append(issue.key)

            except Exception as e:
                logger.error(f"Failed to fetch issues for chunk starting at {i}: {e}")
                # Continue processing remaining chunks even if one fails
                continue

        if not keys_to_close:
            logger.info(f"No {type_label} initiatives need to be closed. All active initiatives are still open")
            return []

        # Update database to close the initiatives
        # SAFETY: Only updates tbl_initiative_issue_keys metadata, never touches burndown data
        today = datetime.now().date()

        with conn.cursor() as cursor:
            logger.database(f"Closing {len(keys_to_close)} {type_label} initiatives in tbl_initiative_issue_keys")
            logger.info(f"Setting eff_end_date = {today} and active_flag = false for: {', '.join(keys_to_close)}")

            update_query = """
                UPDATE tbl_initiative_issue_keys
                SET eff_end_date = %s, active_flag = false
                WHERE issue_key = ANY(%s)
            """
            cursor.execute(update_query, (today, keys_to_close))
            conn.commit()

            logger.success(f"Successfully closed {len(keys_to_close)} {type_label} initiatives")
            logger.info(f"Closed initiatives: {', '.join(keys_to_close)}")

        return keys_to_close

    except Exception as e:
        conn.rollback()
        logger.exception(f"Failed to close completed {type_label} initiatives: {e}")
        return []
    finally:
        db_pool.putconn(conn)


def close_completed_iris_initiatives(jira, db_pool):
    """
    Checks all active IRIS initiatives and closes them if they are in a closed statusCategory.
    Sets eff_end_date to current date and active_flag to false for closed initiatives.

    This is a wrapper around close_completed_initiatives() for backward compatibility.
    """
    return close_completed_initiatives(jira, db_pool, initiative_type='IRIS')


def close_completed_orchdept_initiatives(jira, db_pool):
    """
    Checks all active ORCHDEPT initiatives and closes them if they are in a closed statusCategory.
    Sets eff_end_date to current date and active_flag to false for closed initiatives.

    This wrapper focuses specifically on ORCHDEPT epics (issue_key ~ '^ORCHDEPT-\\d+$').
    """
    return close_completed_initiatives(jira, db_pool, initiative_type='ORCHDEPT')


def sync_initiatives_from_jql(jira, db_pool):
    """Fetches initiatives from a JQL query and inserts any new ones into the database."""
    log_section_header(logger, "INITIATIVE SYNC FROM JQL")

    jql = os.getenv('JIRA_INITIATIVE_JQL')
    if not jql:
        logger.warning("JIRA_INITIATIVE_JQL environment variable not set. Skipping initiative sync")
        return

    iris_labels_str = os.getenv('JIRA_IRIS_LABELS', '')
    iris_labels_set = {label.strip() for label in iris_labels_str.split(',') if label.strip()}

    logger.searching(f"Fetching initiatives from Jira with JQL")
    logger.debug(f"Query: {jql}")

    jira_initiatives = jira.search_issues(jql, fields=["key", "labels"], maxResults=False)
    logger.info(f"Found {len(jira_initiatives)} potential initiatives in Jira")

    existing_db_keys = set(db_utils.fetch_initiative_keys(db_pool))
    logger.info(f"Found {len(existing_db_keys)} existing initiatives in the database")

    new_initiatives_to_insert = []
    today = datetime.now().date()
    far_future_date = '9999-12-31'

    for issue in jira_initiatives:
        if issue.key not in existing_db_keys:
            issue_labels = set(issue.fields.labels)
            is_iris = not iris_labels_set.isdisjoint(issue_labels)

            logger.info(f"Found new initiative to insert: {issue.key} (IRIS: {is_iris})")
            new_initiatives_to_insert.append(
                (issue.key, today, far_future_date, is_iris)
            )

    if not new_initiatives_to_insert:
        logger.info("No new initiatives to insert. Database is up-to-date")
        return

    conn = db_pool.getconn()
    try:
        with conn.cursor() as cursor:
            logger.database(f"Inserting {len(new_initiatives_to_insert)} new initiatives into tbl_initiative_issue_keys")
            insert_query = """
                INSERT INTO tbl_initiative_issue_keys (issue_key, eff_start_date, eff_end_date, "IRIS")
                VALUES %s
            """
            psycopg2.extras.execute_values(cursor, insert_query, new_initiatives_to_insert)
            conn.commit()
            logger.success("Successfully inserted new initiatives")
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to insert new initiatives into database: {e}")
    finally:
        db_pool.putconn(conn)


def refresh_iris_flags(jira, db_pool):
    """
    Refresh the IRIS flag for all initiatives by checking current Jira labels.

    Queries JIRA_INITIATIVE_JQL and updates the "IRIS" column in tbl_initiative_issue_keys
    based on whether each epic has any of the JIRA_IRIS_LABELS labels.

    Also inserts any new epics found in the JQL that don't exist in the table yet.
    """
    log_section_header(logger, "REFRESH IRIS FLAGS")

    jql = os.getenv('JIRA_INITIATIVE_JQL')
    if not jql:
        logger.warning("JIRA_INITIATIVE_JQL not set, skipping IRIS flag refresh")
        return

    iris_labels_str = os.getenv('JIRA_IRIS_LABELS', '')
    iris_labels_set = {label.strip() for label in iris_labels_str.split(',') if label.strip()}
    if not iris_labels_set:
        logger.warning("JIRA_IRIS_LABELS not set, skipping IRIS flag refresh")
        return

    logger.info(f"Refreshing IRIS flags using labels: {iris_labels_set}")

    # Query Jira for all initiatives with their labels
    jira_initiatives = jira.search_issues(jql, fields=["key", "labels"], maxResults=False)
    logger.info(f"Found {len(jira_initiatives)} initiatives from JQL")

    # Build dict of epic_key -> is_iris
    epic_iris_map = {}
    for issue in jira_initiatives:
        issue_labels = set(issue.fields.labels)
        is_iris = not iris_labels_set.isdisjoint(issue_labels)
        epic_iris_map[issue.key] = is_iris

    iris_keys = [k for k, v in epic_iris_map.items() if v]
    non_iris_keys = [k for k, v in epic_iris_map.items() if not v]

    logger.info(f"IRIS epics: {len(iris_keys)}, non-IRIS epics: {len(non_iris_keys)}")

    # Update database
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            # First, find which epics already exist in the table
            all_jql_keys = list(epic_iris_map.keys())
            cur.execute(
                "SELECT issue_key FROM tbl_initiative_issue_keys WHERE issue_key = ANY(%s)",
                (all_jql_keys,)
            )
            existing_keys = {row[0] for row in cur.fetchall()}
            missing_keys = set(all_jql_keys) - existing_keys

            # Insert any missing epics
            if missing_keys:
                today = datetime.now().date()
                far_future_date = '9999-12-31'
                new_initiatives = [
                    (key, today, far_future_date, epic_iris_map[key])
                    for key in missing_keys
                ]
                insert_query = """
                    INSERT INTO tbl_initiative_issue_keys (issue_key, eff_start_date, eff_end_date, "IRIS")
                    VALUES %s
                """
                psycopg2.extras.execute_values(cur, insert_query, new_initiatives)
                logger.info(f"Inserted {len(missing_keys)} new initiatives: {sorted(missing_keys)}")

            # Set IRIS=true for epics with IRIS labels
            if iris_keys:
                cur.execute(
                    """
                    UPDATE tbl_initiative_issue_keys
                    SET "IRIS" = true
                    WHERE issue_key = ANY(%s)
                    """,
                    (iris_keys,)
                )
                logger.debug(f"Set IRIS=true for {cur.rowcount} epics")

            # Set IRIS=false for epics without IRIS labels
            if non_iris_keys:
                cur.execute(
                    """
                    UPDATE tbl_initiative_issue_keys
                    SET "IRIS" = false
                    WHERE issue_key = ANY(%s)
                    """,
                    (non_iris_keys,)
                )
                logger.debug(f"Set IRIS=false for {cur.rowcount} epics")

        conn.commit()
        logger.success("IRIS flags refreshed successfully")
    except Exception as e:
        conn.rollback()
        logger.exception(f"Failed to refresh IRIS flags: {e}")
    finally:
        db_pool.putconn(conn)


def is_issue_valid(issue, allowed_projects_set: set) -> bool:
    """Checks if an issue is in an allowed project and was updated recently."""
    if issue.fields.project.key not in allowed_projects_set:
        return False
    try:
        updated_dt = parse_date(issue.fields.updated).replace(tzinfo=None)
        if updated_dt < SIX_MONTHS_AGO:
            return False
    except (TypeError, ValueError):
        return False
    return True


def fetch_issues_in_batch(jira, keys: set, chunk_size: int = 100) -> dict:
    """Fetches a set of issues from Jira using batched JQL queries."""
    if not keys:
        return {}
    
    all_results = {}
    key_list = list(keys)
    logger.processing(f"Batch fetching {len(key_list)} issues in chunks of {chunk_size}")

    for i in range(0, len(key_list), chunk_size):
        chunk = key_list[i:i + chunk_size]
        jql = f"key in ({','.join(f'\"{k}\"' for k in chunk)})"
        
        try:
            results = jira.search_issues(
                jql, maxResults=len(chunk),
                fields="key,summary,issuetype,status,assignee,created,updated,issuelinks,parent,subtasks,project,customfield_10002"
            )
            for issue in results:
                all_results[issue.key] = issue
            logger.debug(f"Fetched chunk {i//chunk_size + 1}, found {len(results)} issues")
        except Exception as e:
            logger.error(f"Failed to fetch a chunk of issues with JQL: {jql}. Error: {e}")
            continue
            
    logger.info(f"Total issues fetched: {len(all_results)}")
    return all_results


def store_issues_bulk(db_pool, issues_to_store: dict):
    """Stores a dictionary of issues in the database by separating inserts and updates."""
    if not issues_to_store:
        logger.info("No new issues to store in tbl_initiative_children")
        return

    logger.database("Starting bulk store operation")
    
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cursor:
            logger.info("Fetching existing issue keys from tbl_initiative_children")
            cursor.execute("SELECT issue_key FROM tbl_initiative_children")
            existing_keys = {row[0] for row in cursor.fetchall()}
            logger.info(f"Found {len(existing_keys)} existing child keys")

            rows_to_insert = []
            rows_to_update = []

            for initiative_key, issue in issues_to_store.values():
                story_points = getattr(issue.fields, 'customfield_10002', 0) or 0
                assignee = issue.fields.assignee.displayName if issue.fields.assignee else 'Unassigned'
                
                data_tuple = (
                    initiative_key, issue.key, issue.fields.summary, issue.fields.issuetype.name,
                    issue.fields.status.name, assignee, issue.fields.created, issue.fields.updated,
                    float(story_points), datetime.now()
                )

                if issue.key in existing_keys:
                    rows_to_update.append(data_tuple)
                else:
                    rows_to_insert.append(data_tuple)
            
            if rows_to_insert:
                logger.database(f"Inserting {len(rows_to_insert)} new records into tbl_initiative_children")
                insert_query = """
                    INSERT INTO tbl_initiative_children (
                        initiative_issue_key, issue_key, summary, issue_type, status, assignee, 
                        created, updated, story_points, effective_dttm
                    ) VALUES %s
                """
                psycopg2.extras.execute_values(cursor, insert_query, rows_to_insert)
                logger.success("Bulk insert complete")

            if rows_to_update:
                logger.database(f"Updating {len(rows_to_update)} existing records in tbl_initiative_children")
                update_query = """
                    UPDATE tbl_initiative_children AS t SET
                        initiative_issue_key = v.initiative_issue_key, summary = v.summary,
                        issue_type = v.issue_type, status = v.status, assignee = v.assignee,
                        created = v.created::timestamp, updated = v.updated::timestamp, 
                        story_points = v.story_points, effective_dttm = v.effective_dttm
                    FROM (VALUES %s) AS v(
                        initiative_issue_key, issue_key, summary, issue_type, status, assignee, 
                        created, updated, story_points, effective_dttm
                    ) WHERE t.issue_key = v.issue_key;
                """
                psycopg2.extras.execute_values(cursor, update_query, rows_to_update)
                logger.success("Bulk update complete")

            conn.commit()
            
    except Exception as e:
        conn.rollback()
        logger.exception(f"Database bulk operation for tbl_initiative_children failed: {e}")
    finally:
        db_pool.putconn(conn)


def main():
    """Main function to fetch and store initiative-related issues."""
    log_section_header(logger, "INITIATIVE CHILDREN ANALYSIS")

    jira = get_jira_client()
    if not jira:
        return

    db_pool = db_utils.get_connection_pool()

    sync_initiatives_from_jql(jira, db_pool)
    close_completed_iris_initiatives(jira, db_pool)

    logger.start("Proceeding to fetch child issues for all initiatives")
    allowed_projects_str = os.getenv("JIRA_PROJECTS", "")
    allowed_projects = {proj.strip() for proj in allowed_projects_str.split(',') if proj.strip()}
    
    initial_keys = db_utils.fetch_initiative_keys(db_pool)
    if not initial_keys:
        logger.warning("No initiative keys found in the database after sync")
        return
    
    logger.info(f"Starting with {len(initial_keys)} initiative keys")
        
    all_related_issues = {} 
    visited_keys = set()
    
    keys_to_fetch = {key: key for key in initial_keys}
    
    depth = 0
    while keys_to_fetch and depth <= MAX_RECURSION_DEPTH:
        logger.info(f"Recursion Depth: {depth}. Keys to fetch: {len(keys_to_fetch)}")
        
        fetched_issues_map = fetch_issues_in_batch(jira, set(keys_to_fetch.keys()))
        visited_keys.update(keys_to_fetch.keys())
        
        next_keys_to_fetch = {} 

        for key, issue in fetched_issues_map.items():
            try:
                if key not in keys_to_fetch:
                    logger.warning(f"Skipping issue {key} as it was not in the expected fetch list")
                    continue
                
                root_initiative_key = keys_to_fetch[key]
                
                if not is_issue_valid(issue, allowed_projects):
                    continue

                if key not in all_related_issues:
                    all_related_issues[key] = (root_initiative_key, issue)

                for link in getattr(issue.fields, "issuelinks", []):
                    if getattr(link, 'type', None) and link.type.name in ALLOWED_LINK_TYPES:
                        linked_issue_obj = getattr(link, "inwardIssue", None) or getattr(link, "outwardIssue", None)
                        if linked_issue_obj and linked_issue_obj.key not in visited_keys:
                            next_keys_to_fetch[linked_issue_obj.key] = root_initiative_key
                
                if issue.fields.issuetype.name == "Epic":
                    six_months_str = SIX_MONTHS_AGO.strftime("%Y-%m-%d")
                    jql = f'"Epic Link" = "{issue.key}" AND updated >= "{six_months_str}"'
                    try:
                        epic_children = jira.search_issues(jql, fields="key") or []
                        for child in epic_children:
                            if child.key not in visited_keys:
                                next_keys_to_fetch[child.key] = root_initiative_key
                    except Exception as e:
                        logger.error(f"Failed to fetch children for Epic {issue.key}: {e}")
            
            except Exception as e:
                logger.exception(f"An unexpected error occurred while processing issue {key}")
                continue

        keys_to_fetch = next_keys_to_fetch
        depth += 1
        
    if depth > MAX_RECURSION_DEPTH:
        logger.warning(f"Reached max recursion depth of {MAX_RECURSION_DEPTH}")
    
    logger.info(f"Found {len(all_related_issues)} total related issues")
    store_issues_bulk(db_pool, all_related_issues)
    logger.complete("Initiative children analysis completed successfully")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    from logging_config import setup_logging
    setup_logging()
    
    main()