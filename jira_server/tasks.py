import os
from datetime import datetime
from jira import JIRA
import logging

# This assumes the server is run from the 'jira_server' directory.
from jira_data_analysis import (jira_processor,
    initiative_children,
    investment_trends,
    db_utils)
from jira_automation import (create_rca_subtasks,
    data_quality_report,
    customer_analysis,
    derive_platform_version,
    ldap_manager_report,
    collect_bug_snapshots,
    generate_bug_charts)

# --- Get a logger that inherits the root configuration ---
logger = logging.getLogger(__name__)

# --- Use a more robust import structure for each module ---
# This prevents one failed import from affecting the others.
try:
    from jira_automation import jira_icebox as jira_automation_app
except ImportError:
    jira_automation_app = None
    logger.warning("Could not import jira_automation.jira_icebox. The icebox task will not be available.")

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


# ... (Apply the same logger pattern to all other task functions) ...
def run_initiative_analysis_task():
    logger.info("Starting initiative analysis task...")
    try:
        initiative_children.main()
        logger.info("Initiative analysis task completed successfully.")
    except Exception as e:
        logger.error(f"An error occurred during initiative analysis: {e}")

def run_investment_trends_task():
    logger.info("Starting investment trends task...")
    try:
        investment_trends.main()
        logger.info("Investment trends task completed successfully.")
    except Exception as e:
        logger.error(f"An error occurred during investment trends generation: {e}")

def check_if_release_run_is_due():
    logger.info("Checking if a release run is due...")
    db_conn_pool = None
    try:
        db_conn_pool = db_utils.get_connection_pool()
        is_due = db_utils.release_run_check(db_conn_pool)
        if is_due:
            logger.info("Check result: Release run is due.")
        else:
            logger.info("Check result: Release run is not yet due.")
        return is_due
    except Exception as e:
        logger.error(f"Failed to check release run status: {e}")
        return False

def run_jira_icebox_task():
    start_time = datetime.now()
    logger.info(f"Starting Jira icebox task at {start_time.isoformat()}...")
    if not jira_automation_app or not hasattr(jira_automation_app, 'main'):
        logger.error("The 'jira_automation.app' module or its 'main' function is not available.")
        return
    try:
        jira_automation_app.main()
        logger.info("Jira icebox task completed successfully.")
    except Exception as e:
        logger.error(f"An error occurred during the Jira icebox task: {e}")
    finally:
        end_time = datetime.now()
        logger.info(f"Jira icebox task finished at {end_time.isoformat()}. Duration: {end_time - start_time}")

def run_ticket_aging_task():
    start_time = datetime.now()
    logger.info(f"Starting Jira ticket aging task at {start_time.isoformat()}...")
    if not ticket_aging or not hasattr(ticket_aging, 'main'):
        logger.error("The 'jira_automation.ticket_aging' module or its 'main' function is not available.")
        return
    try:
        ticket_aging.main()
        logger.info("Jira ticket aging task completed successfully.")
    except Exception as e:
        logger.error(f"An error occurred during the Jira ticket aging task: {e}")
    finally:
        end_time = datetime.now()
        logger.info(f"Jira ticket aging task finished at {end_time.isoformat()}. Duration: {end_time - start_time}")

def run_daily_pushes_task():
    start_time = datetime.now()
    logger.info(f"Starting daily push report task at {start_time.isoformat()}...")
    if not daily_pushes or not hasattr(daily_pushes, 'main'):
        logger.error("The 'jira_automation.daily_pushes' module or its 'main' function is not available.")
        return
    try:
        daily_pushes.main()
        logger.info("Daily push report task completed successfully.")
    except Exception as e:
        logger.error(f"An error occurred during the daily push report task: {e}")
    finally:
        end_time = datetime.now()
        logger.info(f"Daily push report task finished at {end_time.isoformat()}. Duration: {end_time - start_time}")

def run_rca_subtask_creation_task():
    start_time = datetime.now()
    logger.info(f"Starting RCA sub-task creation task at {start_time.isoformat()}...")
    if not create_rca_subtasks or not hasattr(create_rca_subtasks, 'main'):
        logger.error("The 'jira_automation.create_rca_subtasks' module or its 'main' function is not available.")
        return
    try:
        create_rca_subtasks.main()
        logger.info("RCA sub-task creation task completed successfully.")
    except Exception as e:
        logger.error(f"An error occurred during the RCA sub-task creation task: {e}")
    finally:
        end_time = datetime.now()
        logger.info(f"RCA sub-task creation task finished at {end_time.isoformat()}. Duration: {end_time - start_time}")

def run_derive_platform_version_task():
    start_time = datetime.now()
    logger.info(f"Starting platform version derivation task at {start_time.isoformat()}...")
    if not derive_platform_version or not hasattr(derive_platform_version, 'main'):
        logger.error("The 'jira_automation.derive_platform_version' module or its 'main' function is not available.")
        return
    try:
        derive_platform_version.main()
        logger.info("Platform version derivation task completed successfully.")
    except Exception as e:
        logger.error(f"An error occurred during the platform version derivation task: {e}")
    finally:
        end_time = datetime.now()
        logger.info(f"Platform version derivation task finished at {end_time.isoformat()}. Duration: {end_time - start_time}")

def run_data_quality_report_task():
    start_time = datetime.now()
    logger.info(f"Starting data quality report task at {start_time.isoformat()}...")
    logger.info("Step 1: Running platform version derivation...")
    run_derive_platform_version_task()
    logger.info("Step 1 complete.")
    logger.info("Step 2: Generating data quality reports...")
    if not data_quality_report or not hasattr(data_quality_report, 'main'):
        logger.error("The 'jira_automation.data_quality_report' module or its 'main' function is not available.")
        return
    try:
        data_quality_report.main()
        logger.info("Data quality report generation completed successfully.")
    except Exception as e:
        logger.error(f"An error occurred during the data quality report generation: {e}")
    finally:
        end_time = datetime.now()
        logger.info(f"Data quality report task finished at {end_time.isoformat()}. Duration: {end_time - start_time}")

def run_customer_analysis_task():
    start_time = datetime.now()
    logger.info(f"Starting customer analysis task at {start_time.isoformat()}...")
    if not customer_analysis or not hasattr(customer_analysis, 'main'):
        logger.error("The 'jira_automation.customer_analysis' module or its 'main' function is not available.")
        return
    try:
        customer_analysis.main()
        logger.info("Customer analysis task completed successfully.")
    except Exception as e:
        logger.error(f"An error occurred during the customer analysis task: {e}")
    finally:
        end_time = datetime.now()
        logger.info(f"Customer analysis task finished at {end_time.isoformat()}. Duration: {end_time - start_time}")

# --- Task function for the LDAP report job ---
def run_ldap_report_task():
    """
    Worker task to generate the LDAP manager report.
    """
    start_time = datetime.now()
    logger.info(f"Starting LDAP manager report task at {start_time.isoformat()}...")

    if not ldap_manager_report or not hasattr(ldap_manager_report, 'main'):
        logger.error("The 'jira_automation.ldap_manager_report' module or its 'main' function is not available.")
        return

    try:
        ldap_manager_report.main()
        logger.info("LDAP manager report task completed successfully.")
    except Exception as e:
        logger.error(f"An error occurred during the LDAP manager report task: {e}")
    finally:
        end_time = datetime.now()
        logger.info(f"LDAP manager report task finished at {end_time.isoformat()}. Duration: {end_time - start_time}")

def run_bug_snapshot_collection_task():
    """Worker task to collect daily bug snapshot data."""
    logger.info("Starting bug snapshot collection task...")
    try:
        collect_bug_snapshots.main()
        logger.info("Bug snapshot collection task completed successfully.")
    except Exception as e:
        logger.error(f"An error occurred during snapshot collection: {e}")

def run_bug_chart_generation_task():
    """Worker task to generate the bug trend charts."""
    logger.info("Starting bug chart generation task...")
    try:
        # Before generating charts, it's a good practice to ensure
        # the data is up-to-date.
        logger.info("Running snapshot collection first to ensure data is fresh...")
        collect_bug_snapshots.main()
        
        logger.info("Now generating charts...")
        generate_bug_charts.main()
        logger.info("Bug chart generation task completed successfully.")
    except Exception as e:
        logger.error(f"An error occurred during chart generation: {e}")
