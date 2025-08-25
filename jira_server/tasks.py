import os
from datetime import datetime
from jira import JIRA

# This assumes the server is run from the 'jira_server' directory.
from jira_data_analysis import jira_processor
from jira_data_analysis import initiative_children
from jira_data_analysis import investment_trends
from jira_data_analysis import db_utils
from jira_automation import create_rca_subtasks
from jira_automation import data_quality_report
from jira_automation import customer_analysis
from jira_automation import derive_platform_version

# --- FIX: Use a more robust import structure for each module ---
# This prevents one failed import from affecting the others.
try:
    from jira_automation import app as jira_automation_app
except ImportError:
    jira_automation_app = None
    print("WARNING: Could not import 'jira_automation.app'. The icebox job will be unavailable.")

try:
    from jira_automation import ticket_aging
except ImportError:
    ticket_aging = None
    print("WARNING: Could not import 'jira_automation.ticket_aging'. The ticket aging job will be unavailable.")

try:
    from jira_automation import daily_pushes
except ImportError:
    daily_pushes = None
    print("WARNING: Could not import 'jira_automation.daily_pushes'. The daily pushes job will be unavailable.")


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
# --- Task function for the daily push report ---
def run_daily_pushes_task():
    """
    Worker task to generate the daily push report.
    """
    start_time = datetime.now()
    print(f"Starting daily push report task at {start_time.isoformat()}...")

    if not daily_pushes or not hasattr(daily_pushes, 'main'):
        print("ERROR: The 'jira_automation.daily_pushes' module or its 'main' function is not available.")
        return

    try:
        daily_pushes.main()
        print("Daily push report task completed successfully.")
    except Exception as e:
        print(f"An error occurred during the daily push report task: {e}")
    finally:
        end_time = datetime.now()
        print(f"Daily push report task finished at {end_time.isoformat()}. Duration: {end_time - start_time}")

def run_rca_subtask_creation_task():
    """
    Worker task to create RCA sub-tasks for critical bugs.
    """
    start_time = datetime.now()
    print(f"Starting RCA sub-task creation task at {start_time.isoformat()}...")

    if not create_rca_subtasks or not hasattr(create_rca_subtasks, 'main'):
        print("ERROR: The 'jira_automation.create_rca_subtasks' module or its 'main' function is not available.")
        return

    try:
        create_rca_subtasks.main()
        print("RCA sub-task creation task completed successfully.")
    except Exception as e:
        print(f"An error occurred during the RCA sub-task creation task: {e}")
    finally:
        end_time = datetime.now()
        print(f"RCA sub-task creation task finished at {end_time.isoformat()}. Duration: {end_time - start_time}")

# --- Task function for the platform version derivation job ---
def run_derive_platform_version_task():
    """
    Worker task to derive and update the Platform Version field for applicable bugs.
    """
    start_time = datetime.now()
    print(f"Starting platform version derivation task at {start_time.isoformat()}...")

    if not derive_platform_version or not hasattr(derive_platform_version, 'main'):
        print("ERROR: The 'jira_automation.derive_platform_version' module or its 'main' function is not available.")
        return

    try:
        derive_platform_version.main()
        print("Platform version derivation task completed successfully.")
    except Exception as e:
        print(f"An error occurred during the platform version derivation task: {e}")
    finally:
        end_time = datetime.now()
        print(f"Platform version derivation task finished at {end_time.isoformat()}. Duration: {end_time - start_time}")

# --- Task function for the data quality report job ---
def run_data_quality_report_task():
    """
    Worker task to generate the daily data quality reports.
    """
    start_time = datetime.now()
    print(f"Starting data quality report task at {start_time.isoformat()}...")

    if not data_quality_report or not hasattr(data_quality_report, 'main'):
        print("ERROR: The 'jira_automation.data_quality_report' module or its 'main' function is not available.")
        return

    try:
        data_quality_report.main()
        print("Data quality report task completed successfully.")
    except Exception as e:
        print(f"An error occurred during the data quality report task: {e}")
    finally:
        end_time = datetime.now()
        print(f"Data quality report task finished at {end_time.isoformat()}. Duration: {end_time - start_time}")
# --- Task function for the customer analysis job ---
def run_customer_analysis_task():
    """
    Worker task to find, update, and report on open customer bugs.
    """
    start_time = datetime.now()
    print(f"Starting customer analysis task at {start_time.isoformat()}...")

    if not customer_analysis or not hasattr(customer_analysis, 'main'):
        print("ERROR: The 'jira_automation.customer_analysis' module or its 'main' function is not available.")
        return

    try:
        customer_analysis.main()
        print("Customer analysis task completed successfully.")
    except Exception as e:
        print(f"An error occurred during the customer analysis task: {e}")
    finally:
        end_time = datetime.now()
        print(f"Customer analysis task finished at {end_time.isoformat()}. Duration: {end_time - start_time}")
