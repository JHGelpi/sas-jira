#!/usr/bin/env python3
"""
Check the owner of tbl_bug_snapshots and current user permissions.
"""

import os
from dotenv import load_dotenv
from jira_data_analysis import db_utils

# Load environment variables
load_dotenv()

def check_table_info():
    """Check table ownership and permissions."""

    pool = db_utils.get_connection_pool()
    conn = pool.getconn()

    try:
        with conn.cursor() as cur:
            print("🔍 Checking table ownership and permissions...")
            print("=" * 70)

            # Check current user
            cur.execute("SELECT current_user;")
            current_user = cur.fetchone()[0]
            print(f"Current database user: {current_user}")
            print()

            # Check table owner
            cur.execute("""
                SELECT
                    schemaname,
                    tablename,
                    tableowner
                FROM pg_tables
                WHERE tablename = 'tbl_bug_snapshots';
            """)
            result = cur.fetchone()
            if result:
                schema, table, owner = result
                print(f"Table: {schema}.{table}")
                print(f"Owner: {owner}")
                print()

                if owner == current_user:
                    print("✅ Current user is the table owner - migration should work")
                else:
                    print(f"⚠️  Current user ({current_user}) is NOT the table owner ({owner})")
                    print()
                    print("Options to fix this:")
                    print(f"  1. Run migration as user '{owner}'")
                    print(f"  2. Have '{owner}' grant ALTER permission to '{current_user}':")
                    print(f"     GRANT ALL ON TABLE tbl_bug_snapshots TO {current_user};")
            else:
                print("❌ Table 'tbl_bug_snapshots' not found!")

            # Check if columns already exist
            print()
            print("Checking for existing columns...")
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'tbl_bug_snapshots'
                AND column_name IN ('summary', 'updated')
                ORDER BY column_name
            """)
            existing = [row[0] for row in cur.fetchall()]

            if existing:
                print(f"⚠️  Columns already exist: {', '.join(existing)}")
                print("   Migration may have already been run!")
            else:
                print("✅ Columns do not exist yet - migration is needed")

    except Exception as e:
        print(f"❌ Error: {e}")
        raise
    finally:
        pool.putconn(conn)


if __name__ == "__main__":
    check_table_info()
