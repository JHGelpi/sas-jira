#!/usr/bin/env python3
"""Fix COMPDIV-30 -> COMPLANG-758 key migration and close it."""

import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent / 'jira_server'
sys.path.insert(0, str(project_root))

# Load environment
from dotenv import load_dotenv
load_dotenv(project_root / '.env')

# Import database utilities
from jira_data_analysis import db_utils

def main():
    """Fix COMPDIV-30 issue key and close it."""
    pool = db_utils.get_connection_pool()
    conn = pool.getconn()

    try:
        print("Step 1: Updating issue_key from COMPDIV-30 to COMPLANG-758...")
        with conn.cursor() as cur:
            # Update the issue key
            cur.execute("""
                UPDATE tbl_initiative_issue_keys
                SET issue_key = 'COMPLANG-758'
                WHERE issue_key = 'COMPDIV-30'
            """)
            conn.commit()
            print(f"  ✓ Updated issue_key to COMPLANG-758")

        print("\nStep 2: Closing COMPLANG-758 (formerly COMPDIV-30)...")
        today = datetime.now().date()
        with conn.cursor() as cur:
            # Close the initiative
            cur.execute("""
                UPDATE tbl_initiative_issue_keys
                SET active_flag = false,
                    eff_end_date = %s
                WHERE issue_key = 'COMPLANG-758'
            """, (today,))
            conn.commit()
            print(f"  ✓ Set active_flag = false")
            print(f"  ✓ Set eff_end_date = {today}")

        print("\nStep 3: Verifying changes...")
        with conn.cursor() as cur:
            cur.execute("""
                SELECT issue_key, "IRIS", active_flag, eff_end_date
                FROM tbl_initiative_issue_keys
                WHERE issue_key = 'COMPLANG-758'
            """)
            row = cur.fetchone()
            if row:
                print(f"  issue_key: {row[0]}")
                print(f"  IRIS: {row[1]}")
                print(f"  active_flag: {row[2]}")
                print(f"  eff_end_date: {row[3]}")
                print("\n✓ COMPLANG-758 successfully updated and closed!")
            else:
                print("  ✗ Warning: Could not find COMPLANG-758 after update")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        conn.rollback()
    finally:
        pool.putconn(conn)

if __name__ == '__main__':
    response = input("This will update COMPDIV-30 -> COMPLANG-758 and mark it as closed. Continue? (yes/no): ")
    if response.lower() in ['yes', 'y']:
        main()
    else:
        print("Cancelled.")
