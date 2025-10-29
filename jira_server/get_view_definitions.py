#!/usr/bin/env python3
"""
Retrieve database view definitions for ship_cadence migration.

This script fetches the current definitions of views that need to be updated
to include the ship_cadence column.
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


def get_view_definition(engine, view_name):
    """Retrieve the definition of a specific view."""
    query = text("""
        SELECT definition
        FROM pg_views
        WHERE viewname = :view_name
        AND schemaname = 'public'
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {"view_name": view_name})
        row = result.fetchone()
        if row:
            return row[0]
        return None


def save_view_definition(view_name, definition, output_dir):
    """Save view definition to a SQL file."""
    filename = os.path.join(output_dir, f"{view_name}_original.sql")

    with open(filename, 'w') as f:
        f.write(f"-- Original definition of {view_name}\n")
        f.write(f"-- Retrieved: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"CREATE OR REPLACE VIEW {view_name} AS\n")
        f.write(definition)
        f.write(";\n")

    logger.success(f"Saved definition to {filename}")
    return filename


def main():
    """Main entry point."""
    log_section_header(logger, "VIEW DEFINITION RETRIEVAL")
    logger.start("Retrieving view definitions for ship_cadence migration")

    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)

    # Create output directory
    output_dir = os.path.join(os.path.dirname(__file__), "view_definitions")
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"Output directory: {output_dir}")

    try:
        engine = create_engine(db_url)
        logger.success("Connected to database")

        # Views to retrieve
        views = [
            'view_jira_sprint_data',
            'view_jira_curr_record',
            'view_dedup_investment_flags'
        ]

        for view_name in views:
            logger.processing(f"Retrieving definition for {view_name}")
            definition = get_view_definition(engine, view_name)

            if definition:
                save_view_definition(view_name, definition, output_dir)

                # Print summary
                print(f"\n{'='*80}")
                print(f"View: {view_name}")
                print(f"{'='*80}")
                print(f"Length: {len(definition)} characters")
                print(f"First 200 characters:")
                print(definition[:200])
                print("...")
                print()
            else:
                logger.warning(f"View {view_name} not found")

        logger.complete("View definitions retrieved successfully")
        logger.info(f"Check {output_dir}/ for original view definitions")

        print("\n" + "="*80)
        print("NEXT STEPS")
        print("="*80)
        print("1. Review the view definitions in view_definitions/")
        print("2. Create updated versions with ship_cadence column added")
        print("3. Test the updated views on a staging database")
        print("4. Deploy to production")

    except Exception as e:
        logger.error(f"Failed to retrieve view definitions: {e}")
        raise


if __name__ == "__main__":
    main()
