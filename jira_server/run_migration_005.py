#!/usr/bin/env python3
"""
Run migration 005: Add summary and updated columns to tbl_bug_snapshots.
This migration is required for the interactive bug table feature.
"""

import os
from dotenv import load_dotenv
from jira_data_analysis import db_utils

# Load environment variables
load_dotenv()

def run_migration():
    """Run the migration to add summary and updated columns."""

    # Read the migration SQL file
    migration_file = os.path.join(
        os.path.dirname(__file__),
        'schema_migrations',
        '005_add_summary_updated_to_bug_snapshots.sql'
    )

    print(f"📂 Reading migration file: {migration_file}")
    with open(migration_file, 'r') as f:
        migration_sql = f.read()

    pool = db_utils.get_connection_pool()
    conn = pool.getconn()

    try:
        with conn.cursor() as cur:
            print("🔄 Running migration 005: Add summary and updated columns...")
            print("=" * 70)

            # Execute the migration SQL
            cur.execute(migration_sql)

            conn.commit()
            print("=" * 70)
            print("✅ Migration completed successfully!")
            print()

            # Verify the columns were added
            print("🔍 Verifying columns were added...")
            cur.execute("""
                SELECT column_name, data_type, character_maximum_length, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'tbl_bug_snapshots'
                AND column_name IN ('summary', 'updated')
                ORDER BY column_name
            """)
            columns = cur.fetchall()

            if len(columns) == 2:
                print("✅ Verified: Both columns exist in tbl_bug_snapshots")
                print()
                print("Column Details:")
                print("-" * 70)
                for col in columns:
                    col_name, data_type, max_length, nullable = col
                    print(f"  • {col_name}: {data_type}" +
                          (f"({max_length})" if max_length else "") +
                          f" - Nullable: {nullable}")
                print()
                print("✅ Migration 005 completed successfully!")
                print()
                print("📋 Next Steps:")
                print("  1. Collect fresh bug snapshots to populate new fields:")
                print("     curl -X POST http://127.0.0.1:8000/jobs/collect-bug-snapshots")
                print()
                print("  2. Generate updated bug charts:")
                print("     curl -X POST http://127.0.0.1:8000/jobs/generate-bug-charts")
            else:
                print(f"⚠️  Warning: Expected 2 columns, found {len(columns)}")
                print("Please check the migration output above for errors.")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error running migration: {e}")
        raise
    finally:
        pool.putconn(conn)


if __name__ == "__main__":
    run_migration()
