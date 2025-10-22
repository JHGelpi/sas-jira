#!/usr/bin/env python3
"""
Create the tbl_iris_burndown table in the database.
Run this script to set up the IRIS burndown table structure.
"""

import os
from dotenv import load_dotenv
from jira_data_analysis import db_utils

# Load environment variables
load_dotenv()

def create_iris_burndown_table():
    """Create the tbl_iris_burndown table if it doesn't exist."""

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS public.tbl_iris_burndown (
        run_date DATE NOT NULL,
        epic_key VARCHAR(50) NOT NULL,
        bug_points NUMERIC(10,2) DEFAULT 0,
        story_points NUMERIC(10,2) DEFAULT 0,
        task_research_points NUMERIC(10,2) DEFAULT 0,
        total_points NUMERIC(10,2) DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (run_date, epic_key)
    );
    """

    create_epic_index_sql = """
    CREATE INDEX IF NOT EXISTS idx_iris_burndown_epic_key
    ON public.tbl_iris_burndown(epic_key);
    """

    create_date_index_sql = """
    CREATE INDEX IF NOT EXISTS idx_iris_burndown_run_date
    ON public.tbl_iris_burndown(run_date);
    """

    pool = db_utils.get_connection_pool()
    conn = pool.getconn()

    try:
        with conn.cursor() as cur:
            print("Creating tbl_iris_burndown table...")
            cur.execute(create_table_sql)

            print("Creating index on epic_key...")
            cur.execute(create_epic_index_sql)

            print("Creating index on run_date...")
            cur.execute(create_date_index_sql)

            conn.commit()
            print("✅ Successfully created tbl_iris_burndown table and indexes!")

            # Verify the table exists
            cur.execute("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'tbl_iris_burndown'
            """)
            count = cur.fetchone()[0]

            if count == 1:
                print("✅ Verified: tbl_iris_burndown table exists in the database")
            else:
                print("❌ Warning: Could not verify table creation")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error creating table: {e}")
        raise
    finally:
        pool.putconn(conn)


if __name__ == "__main__":
    create_iris_burndown_table()
