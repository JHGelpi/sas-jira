#!/usr/bin/env python3
"""
Add ship_cadence column to tbl_jira_sprint_data.

This script adds the new ship_cadence column, creates an index,
and adds documentation comment.
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
from logging_utils import get_logger, log_section_header

setup_logging()
logger = get_logger(__name__)


def check_column_exists(engine):
    """Check if ship_cadence column already exists."""
    query = text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'tbl_jira_sprint_data'
        AND column_name = 'ship_cadence'
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        return result.fetchone() is not None


def check_index_exists(engine):
    """Check if ship_cadence index already exists."""
    query = text("""
        SELECT indexname
        FROM pg_indexes
        WHERE tablename = 'tbl_jira_sprint_data'
        AND indexname = 'idx_jira_sprint_data_ship_cadence'
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        return result.fetchone() is not None


def add_ship_cadence_column(engine):
    """Add ship_cadence column to tbl_jira_sprint_data."""
    log_section_header(logger, "ADD SHIP_CADENCE COLUMN")
    logger.start("Starting database schema update")

    # Check if column exists
    if check_column_exists(engine):
        logger.warning("ship_cadence column already exists, skipping creation")
    else:
        logger.processing("Adding ship_cadence column to tbl_jira_sprint_data")

        with engine.connect() as conn:
            # Add column
            conn.execute(text("""
                ALTER TABLE tbl_jira_sprint_data
                ADD COLUMN ship_cadence VARCHAR(7)
            """))
            conn.commit()

            logger.success("ship_cadence column added successfully")

            # Add comment
            conn.execute(text("""
                COMMENT ON COLUMN tbl_jira_sprint_data.ship_cadence
                IS 'Latest valid fix version in YYYY.MM format, derived from fix_version field. Represents the ship/release cadence.'
            """))
            conn.commit()

            logger.success("Column comment added")

    # Check if index exists
    if check_index_exists(engine):
        logger.warning("Index idx_jira_sprint_data_ship_cadence already exists, skipping creation")
    else:
        logger.processing("Creating index on ship_cadence column")

        with engine.connect() as conn:
            # Add index
            conn.execute(text("""
                CREATE INDEX idx_jira_sprint_data_ship_cadence
                ON tbl_jira_sprint_data(ship_cadence)
            """))
            conn.commit()

            logger.success("Index created successfully")

    logger.complete("Database schema update completed")


def verify_changes(engine):
    """Verify the column and index were created."""
    logger.processing("Verifying database changes")

    # Check column
    column_exists = check_column_exists(engine)
    if column_exists:
        logger.success("✓ ship_cadence column exists")
    else:
        logger.error("✗ ship_cadence column NOT found")
        return False

    # Check index
    index_exists = check_index_exists(engine)
    if index_exists:
        logger.success("✓ idx_jira_sprint_data_ship_cadence index exists")
    else:
        logger.error("✗ Index NOT found")
        return False

    # Check column details
    query = text("""
        SELECT
            column_name,
            data_type,
            character_maximum_length,
            is_nullable
        FROM information_schema.columns
        WHERE table_name = 'tbl_jira_sprint_data'
        AND column_name = 'ship_cadence'
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        row = result.fetchone()
        if row:
            logger.info(f"Column details: {row.column_name} {row.data_type}({row.character_maximum_length}) NULL={row.is_nullable}")
        else:
            logger.error("Could not fetch column details")
            return False

    return True


def main():
    """Main entry point."""
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)

    try:
        engine = create_engine(db_url)
        logger.success(f"Connected to database")

        # Add column and index
        add_ship_cadence_column(engine)

        # Verify changes
        if verify_changes(engine):
            logger.success("All database changes verified successfully")
        else:
            logger.error("Verification failed")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Failed to update database schema: {e}")
        raise


if __name__ == "__main__":
    main()
