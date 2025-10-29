#!/usr/bin/env python3
"""
Find all database objects (views, functions, materialized views) that reference 'normalized_sprint'.

This script helps identify all database dependencies that need to be updated
when migrating from normalized_sprint to ship_cadence.
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


def find_views_with_normalized_sprint(engine):
    """Find all views that reference normalized_sprint."""
    logger.processing("Searching for views with normalized_sprint")

    query = text("""
        SELECT
            schemaname,
            viewname,
            definition
        FROM pg_views
        WHERE definition ILIKE '%normalized_sprint%'
        AND schemaname = 'public'
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        rows = result.fetchall()

        if rows:
            logger.info(f"Found {len(rows)} view(s) with normalized_sprint")
            for row in rows:
                logger.info(f"  - {row.schemaname}.{row.viewname}")
                print(f"\nView: {row.schemaname}.{row.viewname}")
                print("-" * 80)
                print(row.definition[:500])  # Print first 500 chars
                print("...")
        else:
            logger.info("No views found with normalized_sprint")

    return rows


def find_functions_with_normalized_sprint(engine):
    """Find all functions that reference normalized_sprint."""
    logger.processing("Searching for functions with normalized_sprint")

    query = text("""
        SELECT
            n.nspname AS schema_name,
            p.proname AS function_name,
            pg_get_functiondef(p.oid) AS definition
        FROM pg_proc p
        JOIN pg_namespace n ON p.pronamespace = n.oid
        WHERE pg_get_functiondef(p.oid) ILIKE '%normalized_sprint%'
        AND n.nspname = 'public'
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        rows = result.fetchall()

        if rows:
            logger.info(f"Found {len(rows)} function(s) with normalized_sprint")
            for row in rows:
                logger.info(f"  - {row.schema_name}.{row.function_name}")
                print(f"\nFunction: {row.schema_name}.{row.function_name}")
                print("-" * 80)
                print(row.definition[:500])  # Print first 500 chars
                print("...")
        else:
            logger.info("No functions found with normalized_sprint")

    return rows


def find_matviews_with_normalized_sprint(engine):
    """Find all materialized views that reference normalized_sprint."""
    logger.processing("Searching for materialized views with normalized_sprint")

    query = text("""
        SELECT
            schemaname,
            matviewname,
            definition
        FROM pg_matviews
        WHERE definition ILIKE '%normalized_sprint%'
        AND schemaname = 'public'
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        rows = result.fetchall()

        if rows:
            logger.info(f"Found {len(rows)} materialized view(s) with normalized_sprint")
            for row in rows:
                logger.info(f"  - {row.schemaname}.{row.matviewname}")
                print(f"\nMaterialized View: {row.schemaname}.{row.matviewname}")
                print("-" * 80)
                print(row.definition[:500])  # Print first 500 chars
                print("...")
        else:
            logger.info("No materialized views found with normalized_sprint")

    return rows


def main():
    """Main entry point."""
    log_section_header(logger, "FIND NORMALIZED_SPRINT REFERENCES")
    logger.start("Scanning database for normalized_sprint references")

    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)

    try:
        engine = create_engine(db_url)
        logger.success("Connected to database")

        # Find all database objects
        views = find_views_with_normalized_sprint(engine)
        functions = find_functions_with_normalized_sprint(engine)
        matviews = find_matviews_with_normalized_sprint(engine)

        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Views found: {len(views)}")
        print(f"Functions found: {len(functions)}")
        print(f"Materialized views found: {len(matviews)}")
        print(f"Total database objects: {len(views) + len(functions) + len(matviews)}")

        logger.complete("Scan complete")

    except Exception as e:
        logger.error(f"Failed to scan database: {e}")
        raise


if __name__ == "__main__":
    main()
