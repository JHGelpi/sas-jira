import os
import sys
import psycopg2
from psycopg2 import pool
from datetime import datetime
from dotenv import load_dotenv
from logging_utils import get_logger

logger = get_logger(__name__)
# Load environment variables from a .env file
#load_dotenv()
# 1. Get the absolute path of the directory where the current script is located.
#    For example: /Users/wegelpi/github_repos/sas-jira/jira_server/jira_data_analysis
current_dir = os.path.dirname(os.path.abspath(__file__))

# 2. Get the parent directory's path by going one level up.
#    This will be: /Users/wegelpi/github_repos/sas-jira/jira_server
project_root = os.path.dirname(current_dir)

# 3. Construct the full path to the .env file located in the project root.
dotenv_path = os.path.join(project_root, '.env')

# 4. Load the .env file from the specified path.
#    The script will now have access to all the environment variables.
load_dotenv(dotenv_path=dotenv_path)

# --- Connection Pool Initialization ---

# This function will be called once when the module is first imported.
def initialize_connection_pool():
    """
    Initializes and returns a database connection pool.
    Exits the application if the connection fails.
    """
    db_url = os.getenv('DATABASE_URL')

    if not db_url:
        print("FATAL: DATABASE_URL environment variable is not set. Please check your .env file.")
        sys.exit(1) # Exit the application immediately

    try:
        print("Attempting to initialize database connection pool...")
        pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=20,
            dsn=db_url
        )
        print("Database connection pool initialized successfully.")
        return pool
    except psycopg2.OperationalError as e:
        print(f"FATAL: Could not connect to the database using the provided DATABASE_URL.")
        print(f"Error details: {e}")
        print("Please ensure the database is running and the DATABASE_URL is correct in your .env file.")
        sys.exit(1) # Exit the application immediately

# Initialize the pool when the module is loaded.
CONNECTION_POOL = initialize_connection_pool()

def get_connection_pool():
    """Returns the initialized connection pool."""
    # The application will have already exited if the pool is None,
    # so this check is now for robustness.
    if not CONNECTION_POOL:
        raise ConnectionError("Database pool is not available.")
    return CONNECTION_POOL

# --- Data Loading Utilities ---

def load_sprint_managers(db_pool) -> dict:
    """Loads sprint manager data from the database into a dictionary for quick lookup."""
    managers = {}
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT project, project_owner FROM tbl_jira_project_owners")
            for row in cursor.fetchall():
                managers[row[0]] = row[1]
    except Exception as e:
        print(f"Error loading sprint managers: {e}")
    finally:
        db_pool.putconn(conn)
    return managers

def load_operational_epics(db_pool) -> dict:
    """Loads operational epic data into a dictionary for quick lookup."""
    epics = {}
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT epic, sprint_team FROM tbl_jira_oper_epics")
            for row in cursor.fetchall():
                epics[row[0]] = row[1]
    except Exception as e:
        print(f"Error loading operational epics: {e}")
    finally:
        db_pool.putconn(conn)
    return epics
    
def fetch_initiative_keys(db_pool) -> list:
    """Fetches all initiative issue keys from the database."""
    keys = []
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT issue_key FROM tbl_initiative_issue_keys")
            keys = [row[0] for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error fetching initiative keys: {e}")
    finally:
        db_pool.putconn(conn)
    return keys

# --- Logging and Checks ---

def update_run_log(db_pool, start_time: datetime, end_time: datetime, run_flag: str):
    """Logs the execution details of a run into the database."""
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO tbl_run_log ("execOrigin", "startDTTM", "endDTTM", "sprint", "runType") 
                VALUES (%s, %s, %s, %s, %s);
            """
            # Note: 'sprint' and 'runType' seem to be the same. Consolidating to run_flag.
            log_record = ('python', start_time, end_time, run_flag, run_flag.upper())
            cursor.execute(sql, log_record)
            conn.commit()
            print(f"Successfully logged '{run_flag}' run.")
    except Exception as e:
        conn.rollback()
        print(f"Failed to update run log: {e}")
    finally:
        db_pool.putconn(conn)

def release_run_check(db_pool) -> bool:
    """
    Checks if the latest daily run occurred on or after the target release date,
    and if a release run for that period has not already been completed.
    """
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cursor:
            # 1. Get the target release date (most recent one that has passed)
            cursor.execute("SELECT MAX(release_date) FROM tbl_jira_releases WHERE release_date <= current_date;")
            target_release_date = cursor.fetchone()[0]
            if not target_release_date:
                return False # No applicable releases

            # 2. Get the date of the last 'release' type run
            cursor.execute("""
                SELECT MAX(date("endDTTM")) FROM tbl_run_log WHERE "runType" = 'RELEASE';
            """)
            last_release_run_date = cursor.fetchone()[0]

            # Trigger if a release run has never happened or if it was before the current target release
            if last_release_run_date is None or last_release_run_date < target_release_date:
                return True
            
    except Exception as e:
        print(f"Database error during release check: {e}")
        return False
    finally:
        db_pool.putconn(conn)
    
    return False
