#!/usr/bin/env python3
"""
Optimized backfill for ship_cadence column using bulk updates.

This version fetches all records, computes ship_cadence in Python,
then performs a single bulk UPDATE using a temporary table for maximum performance.

Usage:
    python backfill_ship_cadence_optimized.py [--batch-size 50000] [--dry-run]
"""

import os
import sys
import argparse
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from datetime import datetime
import time

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


def backfill_ship_cadence_bulk(batch_size=50000, dry_run=False):
    """
    Backfill ship_cadence using optimized bulk updates.

    Strategy:
    1. Fetch records in batches
    2. Compute ship_cadence in Python
    3. Use COPY or bulk INSERT into temp table
    4. Single UPDATE FROM temp table
    """
    start_time = datetime.now()

    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        logger.error("DATABASE_URL environment variable not set")
        return False

    engine = create_engine(db_url)

    log_section_header(logger, "BACKFILL SHIP_CADENCE")
    logger.start("Starting optimized ship_cadence backfill process")

    # Get total records
    with engine.connect() as conn:
        total_query = text("SELECT COUNT(*) FROM tbl_jira_sprint_data")
        total = conn.execute(total_query).scalar()
        logger.info(f"Total records in table: {total:,}")

        already_populated_query = text("SELECT COUNT(*) FROM tbl_jira_sprint_data WHERE ship_cadence IS NOT NULL")
        already_populated = conn.execute(already_populated_query).scalar()
        logger.info(f"Records already with ship_cadence: {already_populated:,}")
        logger.info(f"Records to process: {total - already_populated:,}")

    if dry_run:
        logger.warning("DRY RUN MODE - No database updates will be performed")

    # Process in batches
    offset = 0
    total_updated = 0

    while offset < total:
        batch_start = time.time()
        logger.processing(f"Processing batch: {offset:,} to {min(offset + batch_size, total):,}")

        # Fetch batch of records
        fetch_query = text("""
            SELECT issue_key, fix_version
            FROM tbl_jira_sprint_data
            ORDER BY issue_key
            LIMIT :limit OFFSET :offset
        """)

        with engine.connect() as conn:
            result = conn.execute(fetch_query, {"limit": batch_size, "offset": offset})
            batch = result.fetchall()

            if not batch:
                break

            # Compute ship_cadence for all records in Python
            updates = []
            for issue_key, fix_version in batch:
                ship_cadence = normalize_fix_version(fix_version or "")
                updates.append({
                    "issue_key": issue_key,
                    "ship_cadence": ship_cadence if ship_cadence else None
                })

            if not dry_run:
                # Use a single bulk UPDATE with VALUES
                # Build VALUES clause for bulk update
                if updates:
                    # Create temp table for this batch
                    conn.execute(text("""
                        CREATE TEMPORARY TABLE IF NOT EXISTS temp_ship_cadence_updates (
                            issue_key VARCHAR(255),
                            ship_cadence VARCHAR(7)
                        ) ON COMMIT DROP
                    """))
                    conn.execute(text("TRUNCATE TABLE temp_ship_cadence_updates"))

                    # Insert all updates into temp table
                    insert_query = text("""
                        INSERT INTO temp_ship_cadence_updates (issue_key, ship_cadence)
                        VALUES (:issue_key, :ship_cadence)
                    """)
                    conn.execute(insert_query, updates)

                    # Single bulk UPDATE using temp table
                    update_query = text("""
                        UPDATE tbl_jira_sprint_data t
                        SET ship_cadence = u.ship_cadence
                        FROM temp_ship_cadence_updates u
                        WHERE t.issue_key = u.issue_key
                    """)
                    result = conn.execute(update_query)
                    conn.commit()

                    total_updated += result.rowcount

                    batch_time = time.time() - batch_start
                    logger.success(f"Updated {result.rowcount:,} records in {batch_time:.1f}s ({result.rowcount/batch_time:.0f} records/sec)")
            else:
                logger.info(f"[DRY RUN] Would update {len(updates):,} records in this batch")
                # Sample output
                for i, update in enumerate(updates[:5]):
                    logger.debug(f"  {update['issue_key']}: '{update['ship_cadence']}'")
                if len(updates) > 5:
                    logger.debug(f"  ... and {len(updates) - 5} more")
                total_updated += len(updates)

        offset += batch_size

        # Progress report every batch
        logger.info(f"Progress: {min(offset, total):,}/{total:,} records processed ({min(offset, total)/total*100:.1f}%)")

    # Final summary
    total_time = (datetime.now() - start_time).total_seconds()

    logger.info("=" * 80)
    logger.info("BACKFILL SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total records in table: {total:,}")
    logger.info(f"Records updated: {total_updated:,}")
    logger.info(f"Total time: {total_time:.1f}s ({total_updated/total_time:.0f} records/sec)")

    # Verify final state
    with engine.connect() as conn:
        final_count_query = text("SELECT COUNT(*) FROM tbl_jira_sprint_data WHERE ship_cadence IS NOT NULL")
        final_count = conn.execute(final_count_query).scalar()
        logger.info(f"Records with ship_cadence: {final_count:,}")
        logger.success(f"Coverage: {final_count/total*100:.1f}%")

    logger.complete("Backfill process completed")
    return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Backfill ship_cadence column with optimized bulk updates")
    parser.add_argument("--batch-size", type=int, default=50000, help="Number of records per batch (default: 50000)")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without updating database")

    args = parser.parse_args()

    try:
        success = backfill_ship_cadence_bulk(
            batch_size=args.batch_size,
            dry_run=args.dry_run
        )
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
