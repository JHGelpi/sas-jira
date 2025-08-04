import os
from datetime import datetime
from jira import JIRA

# This assumes the server is run from the 'jira_server' directory.
from jira_data_analysis import jira_processor
from jira_data_analysis import initiative_children
from jira_data_analysis import investment_trends
from jira_data_analysis import db_utils

try:
    from jira_automation import app as jira_automation_app
except ImportError:
    jira_automation_app = None
    print("WARNING: Could not import the 'jira_automation' module. The icebox job will not run.")

def get_jira_client():
    """Initializes and returns a JIRA client."""
    return JIRA(
        server=os.getenv('JIRA_URL'),
        token_auth=os.getenv('JIRA_TOKEN')
    )

def run_jira_export_task(run_flag: str):
    """
    The main worker task for fetching issues from Jira and saving them to the database.
    This function is designed to be run in the background.
    """
    start_time = datetime.now()
    print(f"Starting Jira export task for run_flag='{run_flag}' at {start_time.isoformat()}")

    # --- FIX: Initialize db_conn_pool to None before the try block ---
    db_conn_pool = None
    try:
        # This line might fail, causing the UnboundLocalError
        db_conn_pool = db_utils.get_connection_pool()
        jira = get_jira_client()
        
        # Build the appropriate JQL query
        jql_query = jira_processor.build_jql(db_conn_pool, run_flag)
        
        # Fetch all issues in batches
        all_issues = jira_processor.fetch_all_issues(jira, jql_query)
        if not all_issues:
            print("No issues found to process.")
            return

        # Process issues and load them into the database
        jira_processor.process_and_load_issues(db_conn_pool, all_issues, run_flag)
        
    except Exception as e:
        print(f"An error occurred during Jira export task: {e}")
    finally:
        end_time = datetime.now()
        # --- FIX: Check if the pool was successfully created before using it ---
        if db_conn_pool:
            db_utils.update_run_log(db_conn_pool, start_time, end_time, run_flag)
        else:
            print("Could not log run to database because the connection pool was not available.")
            
        print(f"Jira export task finished at {end_time.isoformat()}. Duration: {end_time - start_time}")


def run_initiative_analysis_task():
    """Worker task to update initiative child issues."""
    print("Starting initiative analysis task...")
    try:
        initiative_children.main()
        print("Initiative analysis task completed successfully.")
    except Exception as e:
        print(f"An error occurred during initiative analysis: {e}")

def run_investment_trends_task():
    """Worker task to generate investment trend visualizations."""
    print("Starting investment trends task...")
    try:
        investment_trends.main()
        print("Investment trends task completed successfully.")
    except Exception as e:
        print(f"An error occurred during investment trends generation: {e}")

def check_if_release_run_is_due() -> bool:
    """
    Checks the database to determine if a post-release data run should be triggered.
    """
    print("Checking if a release run is due...")
    db_conn_pool = None
    try:
        db_conn_pool = db_utils.get_connection_pool()
        is_due = db_utils.release_run_check(db_conn_pool)
        if is_due:
            print("Check result: Release run is due.")
        else:
            print("Check result: Release run is not yet due.")
        return is_due
    except Exception as e:
        print(f"Failed to check release run status: {e}")
        return False

def run_jira_icebox_task():
    """
    Worker task to run the Jira icebox automation script.
    """
    start_time = datetime.now()
    print(f"Starting Jira icebox task at {start_time.isoformat()}...")

    # Check if the imported module and its main function are available
    if not jira_automation_app or not hasattr(jira_automation_app, 'main'):
        print("ERROR: The 'jira_automation.app' module or its 'main' function is not available.")
        return

    try:
        # Call the main function from your jira_automation/app.py script
        jira_automation_app.main()
        print("Jira icebox task completed successfully.")
    except Exception as e:
        print(f"An error occurred during the Jira icebox task: {e}")
    finally:
        end_time = datetime.now()
        print("--------------")
        print(f"Jira icebox task finished at {end_time.isoformat()}. Duration: {end_time - start_time}")
        print("--------------")

