#!/usr/bin/env python3
"""
Backfill ship_cadence column for existing records in tbl_jira_sprint_data.

This script processes records in batches to avoid locking the table for extended periods.
It reads fix_version data, applies normalize_fix_version(), and updates ship_cadence.

Usage:
    python backfill_ship_cadence.py [--batch-size 10000] [--dry-run]
"""

import os
import sys
import argparse
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
from jira_data_analysis.jira_utils import normalize_fix_version

setup_logging()
logger = get_logger(__name__)


def check_column_exists(engine):
    """Check if ship_cadence column exists."""
    query = text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'tbl_jira_sprint_data'
        AND column_name = 'ship_cadence'
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        return result.fetchone() is not None


def get_total_records(engine):
    """Get total count of records in tbl_jira_sprint_data."""
    query = text("SELECT COUNT(*) FROM tbl_jira_sprint_data")

    with engine.connect() as conn:
        result = conn.execute(query)
        return result.fetchone()[0]


def get_records_with_ship_cadence(engine):
    """Get count of records that already have ship_cadence populated."""
    query = text("""
        SELECT COUNT(*)
        FROM tbl_jira_sprint_data
        WHERE ship_cadence IS NOT NULL AND ship_cadence != ''
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        return result.fetchone()[0]


def backfill_ship_cadence(engine, batch_size=10000, dry_run=False):
    """
    Backfill ship_cadence for all records in batches.

    Args:
        engine: SQLAlchemy engine
        batch_size: Number of records to process per batch
        dry_run: If True, don't actually update the database
    """
    log_section_header(logger, "BACKFILL SHIP_CADENCE")
    logger.start("Starting ship_cadence backfill process")

    # Check if column exists
    if not check_column_exists(engine):
        logger.error("ship_cadence column does not exist. Run schema migration first.")
        return False

    # Get total records
    total = get_total_records(engine)
    logger.info(f"Total records in table: {total:,}")

    # Get records already populated
    already_populated = get_records_with_ship_cadence(engine)
    logger.info(f"Records already with ship_cadence: {already_populated:,}")
    logger.info(f"Records to process: {total - already_populated:,}")

    if dry_run:
        logger.warning("DRY RUN MODE - No database updates will be performed")

    # Process in batches
    offset = 0
    total_updated = 0
    total_with_valid_version = 0
    total_without_valid_version = 0
    total_skipped = 0

    while offset < total:
        logger.processing(f"Processing batch: {offset:,} to {offset + batch_size:,}")

        # Fetch batch
        fetch_query = text("""
            SELECT issue_key, fix_version, ship_cadence
            FROM tbl_jira_sprint_data
            ORDER BY issue_key
            LIMIT :limit OFFSET :offset
        """)

        with engine.connect() as conn:
            result = conn.execute(fetch_query, {"limit": batch_size, "offset": offset})
            batch = result.fetchall()

            if not batch:
                break

            batch_updates = []

            # Process each record
            for issue_key, fix_version, current_ship_cadence in batch:
                # Skip if already populated (unless we want to recompute)
                if current_ship_cadence:
                    total_skipped += 1
                    continue

                # Calculate new ship_cadence
                new_ship_cadence = normalize_fix_version(fix_version or "")

                if new_ship_cadence:
                    total_with_valid_version += 1
                else:
                    total_without_valid_version += 1

                batch_updates.append({
                    "issue_key": issue_key,
                    "ship_cadence": new_ship_cadence if new_ship_cadence else None
                })

            # Update batch
            if batch_updates and not dry_run:
                update_query = text("""
                    UPDATE tbl_jira_sprint_data
                    SET ship_cadence = :ship_cadence
                    WHERE issue_key = :issue_key
                """)

                conn.execute(update_query, batch_updates)
                conn.commit()

                total_updated += len(batch_updates)
                logger.success(f"Updated {len(batch_updates):,} records in this batch")
            elif batch_updates and dry_run:
                logger.info(f"[DRY RUN] Would update {len(batch_updates):,} records in this batch")
                # Sample output for first 5 records
                for i, update in enumerate(batch_updates[:5]):
                    logger.debug(f"  {update['issue_key']}: '{update['ship_cadence']}'")
                if len(batch_updates) > 5:
                    logger.debug(f"  ... and {len(batch_updates) - 5} more")
                total_updated += len(batch_updates)

        offset += batch_size

        # Progress report every 10 batches
        if (offset // batch_size) % 10 == 0:
            logger.info(f"Progress: {offset:,}/{total:,} records processed ({offset/total*100:.1f}%)")

    # Final summary
    logger.info("=" * 80)
    logger.info("BACKFILL SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total records in table: {total:,}")
    logger.info(f"Records updated: {total_updated:,}")
    logger.info(f"Records skipped (already populated): {total_skipped:,}")
    logger.info(f"Records with valid ship_cadence: {total_with_valid_version:,}")
    logger.info(f"Records without valid ship_cadence: {total_without_valid_version:,}")

    if not dry_run:
        logger.complete("Backfill completed successfully")
    else:
        logger.complete("Dry run completed successfully")

    return True


def verify_backfill(engine):
    """Verify the backfill results."""
    logger.processing("Verifying backfill results")

    # Get statistics
    query = text("""
        SELECT
            COUNT(*) as total_records,
            COUNT(ship_cadence) as records_with_ship_cadence,
            COUNT(CASE WHEN ship_cadence IS NOT NULL AND ship_cadence != '' THEN 1 END) as records_with_valid_ship_cadence,
            COUNT(CASE WHEN fix_version IS NOT NULL AND fix_version != '' THEN 1 END) as records_with_fix_version
        FROM tbl_jira_sprint_data
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        row = result.fetchone()

        logger.info(f"Total records: {row.total_records:,}")
        logger.info(f"Records with ship_cadence (not null): {row.records_with_ship_cadence:,}")
        logger.info(f"Records with valid ship_cadence: {row.records_with_valid_ship_cadence:,}")
        logger.info(f"Records with fix_version: {row.records_with_fix_version:,}")

        # Calculate coverage
        if row.total_records > 0:
            coverage = (row.records_with_ship_cadence / row.total_records) * 100
            logger.info(f"Coverage: {coverage:.1f}%")

    # Sample records
    sample_query = text("""
        SELECT issue_key, fix_version, ship_cadence
        FROM tbl_jira_sprint_data
        WHERE ship_cadence IS NOT NULL
        ORDER BY RANDOM()
        LIMIT 10
    """)

    logger.info("\nSample records with ship_cadence:")
    with engine.connect() as conn:
        result = conn.execute(sample_query)
        for row in result:
            logger.debug(f"  {row.issue_key}: fix_version='{row.fix_version}' → ship_cadence='{row.ship_cadence}'")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Backfill ship_cadence column")
    parser.add_argument("--batch-size", type=int, default=10000, help="Number of records per batch (default: 10000)")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually update the database")
    parser.add_argument("--verify-only", action="store_true", help="Only verify existing data, don't backfill")

    args = parser.parse_args()

    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)

    try:
        engine = create_engine(db_url)
        logger.success("Connected to database")

        if args.verify_only:
            verify_backfill(engine)
        else:
            success = backfill_ship_cadence(engine, batch_size=args.batch_size, dry_run=args.dry_run)

            if success and not args.dry_run:
                verify_backfill(engine)

            if not success:
                sys.exit(1)

    except Exception as e:
        logger.error(f"Failed to backfill ship_cadence: {e}")
        raise


if __name__ == "__main__":
    main()
