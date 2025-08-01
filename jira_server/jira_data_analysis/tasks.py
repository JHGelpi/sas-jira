import os
from datetime import datetime
from jira import JIRA

# Import refactored modules
import jira_processor
import initiative_children
import investment_trends
import db_utils

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

    try:
        jira = get_jira_client()
        db_conn_pool = db_utils.get_connection_pool()
        
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
        db_utils.update_run_log(db_conn_pool, start_time, end_time, run_flag)
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
    try:
        is_due = db_utils.release_run_check()
        if is_due:
            print("Check result: Release run is due.")
        else:
            print("Check result: Release run is not yet due.")
        return is_due
    except Exception as e:
        print(f"Failed to check release run status: {e}")
        return False