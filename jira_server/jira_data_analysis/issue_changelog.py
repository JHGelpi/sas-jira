# jira_data_analysis/issue_changelog.py
"""
Jira issue changelog collection.

This module fetches changelog data from recently updated Jira issues and stores
it in the database for activity analysis. It collects forward only -- no
historical backfill. The dashboard will populate over time as daily runs
accumulate data.

Each run fetches issues updated in the last 24 hours with expand="changelog",
which returns the full changelog for each issue. ON CONFLICT DO NOTHING
prevents duplicates on re-runs.
"""

import os
from datetime import date
from jira import JIRA
from jira_data_analysis import db_utils
from logging_utils import get_logger, log_section_header

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS tbl_issue_changelog (
    id              SERIAL PRIMARY KEY,
    collection_date DATE NOT NULL,
    issue_key       TEXT NOT NULL,
    project_key     TEXT,
    issue_type      TEXT,
    change_id       TEXT NOT NULL,
    author_name     TEXT,
    author_email    TEXT,
    change_created  TIMESTAMPTZ,
    change_date     DATE,
    day_of_week     SMALLINT,
    field_name      TEXT NOT NULL,
    from_string     TEXT,
    to_string       TEXT,
    UNIQUE (issue_key, change_id, field_name)
);
"""

CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_changelog_collection_date ON tbl_issue_changelog (collection_date);",
    "CREATE INDEX IF NOT EXISTS idx_changelog_change_date ON tbl_issue_changelog (change_date);",
    "CREATE INDEX IF NOT EXISTS idx_changelog_project_key ON tbl_issue_changelog (project_key);",
    "CREATE INDEX IF NOT EXISTS idx_changelog_issue_type ON tbl_issue_changelog (issue_type);",
    "CREATE INDEX IF NOT EXISTS idx_changelog_author_email ON tbl_issue_changelog (author_email);",
    "CREATE INDEX IF NOT EXISTS idx_changelog_day_of_week ON tbl_issue_changelog (day_of_week);",
]


def ensure_table_exists(db_pool):
    """Creates the tbl_issue_changelog table and indexes if they do not exist."""
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
            for idx_sql in CREATE_INDEXES_SQL:
                cur.execute(idx_sql)
            conn.commit()
        logger.success("tbl_issue_changelog table and indexes verified")
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to create tbl_issue_changelog: {e}")
        raise
    finally:
        db_pool.putconn(conn)


# ---------------------------------------------------------------------------
# Jira client
# ---------------------------------------------------------------------------

def setup_jira_client():
    """Sets up and returns an authenticated Jira client."""
    try:
        jira_url = os.getenv("JIRA_URL")
        logger.connecting(f"Connecting to Jira server at {jira_url}")

        jira_client = JIRA(
            server=jira_url,
            token_auth=os.getenv("JIRA_TOKEN")
        )

        version = jira_client.server_info()['version']
        logger.success(f"Connected to Jira version {version}")
        return jira_client

    except Exception as e:
        logger.error(f"Failed to connect to Jira: {e}")
        return None


# ---------------------------------------------------------------------------
# Fetch & extract
# ---------------------------------------------------------------------------

def fetch_recently_updated_issues(jira_client, projects):
    """
    Fetches issues updated in the last 24 hours with full changelog.

    Args:
        jira_client: Authenticated JIRA client
        projects: Comma-separated project keys (e.g. "PROJ1,PROJ2")

    Returns:
        List of Jira issue objects with changelog expanded
    """
    jql = f"project in ({projects}) AND updated >= -24h"
    logger.info(f"Fetching recently updated issues: {jql}")

    all_issues = []
    start_at = 0
    batch_size = 50

    while True:
        batch = jira_client.search_issues(
            jql,
            startAt=start_at,
            maxResults=batch_size,
            expand="changelog",
            fields="issuetype,project"
        )

        if not batch:
            break

        all_issues.extend(batch)
        logger.info(f"Fetched {len(all_issues)} issues so far")

        if len(batch) < batch_size:
            break
        start_at += batch_size

    logger.info(f"Total issues fetched: {len(all_issues)}")
    return all_issues


def extract_changelog_entries(issues):
    """
    Extracts changelog entries from Jira issues.

    Args:
        issues: List of Jira issue objects with changelog expanded

    Returns:
        List of tuples ready for database insertion
    """
    from dateutil import parser as dt_parser

    today = date.today()
    entries = []

    for issue in issues:
        issue_key = issue.key
        project_key = issue.fields.project.key if issue.fields.project else None
        issue_type = issue.fields.issuetype.name if issue.fields.issuetype else None

        changelog = issue.changelog
        for history in changelog.histories:
            change_id = str(history.id)

            # Author info
            author = getattr(history, 'author', None)
            author_name = author.displayName if author else None
            author_email = getattr(author, 'emailAddress', None)
            if author_email:
                author_email = author_email.lower()

            # Parse timestamp
            change_created = None
            change_date = None
            day_of_week = None
            try:
                dt = dt_parser.parse(history.created)
                change_created = dt
                change_date = dt.date()
                day_of_week = change_date.weekday()  # 0=Mon..6=Sun
            except Exception:
                pass

            for item in history.items:
                entries.append((
                    today,           # collection_date
                    issue_key,
                    project_key,
                    issue_type,
                    change_id,
                    author_name,
                    author_email,
                    change_created,
                    change_date,
                    day_of_week,
                    item.field,      # field_name
                    item.fromString, # from_string
                    item.toString,   # to_string
                ))

    logger.info(f"Extracted {len(entries)} changelog entries from {len(issues)} issues")
    return entries


# ---------------------------------------------------------------------------
# Database storage
# ---------------------------------------------------------------------------

def store_changelog_entries(db_pool, entries):
    """
    Bulk inserts changelog entries into the database.
    Uses ON CONFLICT DO NOTHING for idempotent re-runs.

    Args:
        db_pool: Database connection pool
        entries: List of tuples from extract_changelog_entries()
    """
    if not entries:
        logger.info("No changelog entries to store")
        return

    from psycopg2.extras import execute_values

    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            sql = """
                INSERT INTO tbl_issue_changelog (
                    collection_date, issue_key, project_key, issue_type,
                    change_id, author_name, author_email,
                    change_created, change_date, day_of_week,
                    field_name, from_string, to_string
                ) VALUES %s
                ON CONFLICT (issue_key, change_id, field_name) DO NOTHING
            """
            execute_values(cur, sql, entries)
            conn.commit()

            logger.success(f"Stored {len(entries)} changelog entries (duplicates skipped)")

    except Exception as e:
        conn.rollback()
        logger.exception(f"Failed to store changelog entries: {e}")
    finally:
        db_pool.putconn(conn)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def main():
    """Orchestrates changelog collection: fetch, extract, store."""
    log_section_header(logger, "CHANGELOG COLLECTION")

    logger.start("Starting changelog collection")

    jira_client = setup_jira_client()
    if not jira_client:
        return

    projects = os.getenv('JIRA_PROJECTS', '')
    if not projects:
        logger.error("JIRA_PROJECTS environment variable is not set")
        return

    db_pool = db_utils.get_connection_pool()
    ensure_table_exists(db_pool)

    issues = fetch_recently_updated_issues(jira_client, projects)
    if not issues:
        logger.info("No recently updated issues found")
        return

    entries = extract_changelog_entries(issues)
    store_changelog_entries(db_pool, entries)

    logger.complete("Changelog collection completed successfully")


if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dotenv_path = os.path.join(project_root, '.env')
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=dotenv_path)

    from logging_config import setup_logging
    setup_logging()

    main()
