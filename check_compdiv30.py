#!/usr/bin/env python3
"""Check COMPDIV-30 status in database."""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent / 'jira_server'
sys.path.insert(0, str(project_root))

# Load environment
from dotenv import load_dotenv
load_dotenv(project_root / '.env')

# Import database utilities
from jira_data_analysis import db_utils

def main():
    """Check COMPDIV-30 status."""
    pool = db_utils.get_connection_pool()
    conn = pool.getconn()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT issue_key, "IRIS", active_flag, eff_end_date
                FROM tbl_initiative_issue_keys
                WHERE issue_key = 'COMPDIV-30'
            """)
            row = cur.fetchone()

            if row:
                print(f"Found COMPDIV-30 in database:")
                print(f"  issue_key: {row[0]}")
                print(f"  IRIS: {row[1]}")
                print(f"  active_flag: {row[2]}")
                print(f"  eff_end_date: {row[3]}")
            else:
                print("COMPDIV-30 NOT found in tbl_initiative_issue_keys")
    finally:
        pool.putconn(conn)

if __name__ == '__main__':
    main()
