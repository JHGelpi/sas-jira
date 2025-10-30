#!/usr/bin/env python3
"""
Check if current database user has necessary permissions for migration.
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dotenv_path = os.path.join(project_root, 'jira_server', '.env')
load_dotenv(dotenv_path=dotenv_path)

# Setup logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from logging_config import setup_logging
from logging_utils import get_logger

setup_logging()
logger = get_logger(__name__)


def check_table_permissions(engine):
    """Check if user can ALTER TABLE tbl_jira_sprint_data."""
    query = text("""
        SELECT
            has_table_privilege(current_user, 'tbl_jira_sprint_data', 'INSERT') as can_insert,
            has_table_privilege(current_user, 'tbl_jira_sprint_data', 'UPDATE') as can_update,
            has_table_privilege(current_user, 'tbl_jira_sprint_data', 'DELETE') as can_delete,
            pg_catalog.has_schema_privilege(current_user, 'public', 'CREATE') as can_create_in_schema
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        row = result.fetchone()

        logger.info("Current user permissions:")
        logger.info(f"  Can INSERT: {row.can_insert}")
        logger.info(f"  Can UPDATE: {row.can_update}")
        logger.info(f"  Can DELETE: {row.can_delete}")
        logger.info(f"  Can CREATE in schema: {row.can_create_in_schema}")

        return row


def check_table_owner(engine):
    """Check who owns tbl_jira_sprint_data."""
    query = text("""
        SELECT tableowner, tablename
        FROM pg_tables
        WHERE tablename = 'tbl_jira_sprint_data'
        AND schemaname = 'public'
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        row = result.fetchone()

        if row:
            logger.info(f"Table owner: {row.tableowner}")
            logger.info(f"Current user: {conn.execute(text('SELECT current_user')).fetchone()[0]}")

            is_owner = row.tableowner == conn.execute(text('SELECT current_user')).fetchone()[0]
            return is_owner, row.tableowner
        return False, None


def main():
    """Main entry point."""
    logger.info("="*80)
    logger.info("CHECKING DATABASE PERMISSIONS FOR MIGRATION")
    logger.info("="*80)

    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)

    try:
        engine = create_engine(db_url)
        logger.success("Connected to database")

        # Check ownership
        is_owner, owner = check_table_owner(engine)

        # Check permissions
        perms = check_table_permissions(engine)

        # Assess ability to run migration
        print("\n" + "="*80)
        print("MIGRATION READINESS ASSESSMENT")
        print("="*80)

        if is_owner:
            print("✅ You are the table owner - can run migration directly")
            print("\nNext steps:")
            print("1. Execute: schema_migrations/001_add_ship_cadence_column.sql")
            print("2. Run: python backfill_ship_cadence.py")
            print("3. Execute: schema_migrations/003_update_views_with_ship_cadence.sql")
        else:
            print(f"❌ You are NOT the table owner (owner: {owner})")
            print("\nOptions:")
            print("1. Ask the database admin to run the migration scripts")
            print("2. Request ALTER permission on tbl_jira_sprint_data")
            print("\nScripts to provide to DBA:")
            print("  - schema_migrations/001_add_ship_cadence_column.sql")
            print("  - schema_migrations/003_update_views_with_ship_cadence.sql")

        print("\nCurrent permissions:")
        print(f"  INSERT: {perms.can_insert}")
        print(f"  UPDATE: {perms.can_update}")
        print(f"  DELETE: {perms.can_delete}")
        print(f"  CREATE: {perms.can_create_in_schema}")

    except Exception as e:
        logger.error(f"Failed to check permissions: {e}")
        raise


if __name__ == "__main__":
    main()
