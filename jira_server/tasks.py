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
    generate_bug_charts,
    run_for_all_compdiv_epics)

# --- Get a logger that inherits the root configuration ---
logger = logging.getLogger(__name__)

# --- Use a more robust import structure for each module ---
try:
    from jira_automation import jira_icebox as jira_automation_app
except ImportError:
    jira_automation_app = None
    logger.warning("Could not import jira_automation.jira_icebox. The icebox task will not be available.")

try:
    from jira_automation import ticket_aging
except ImportError:
    ticket_aging = None
    logger.warning("Could not import 'jira_automation.ticket_aging'. The ticket aging job will be unavailable.")

try:
    from jira_automation import daily_pushes
except ImportError:
    daily_pushes = None
    logger.warning("Could not import 'jira_automation.daily_pushes'. The daily pushes job will be unavailable.")


def get_jira_client():
    """Initializes and returns a JIRA client."""
    return JIRA(
        server=os.getenv('JIRA_URL'),
        token_auth=os.getenv('JIRA_TOKEN')
    )

def run_jira_export_task(run_flag: str):
    """
    The main worker task for the 'daily' data sync.
    """
    start_time = datetime.now()
    logger.info(f"Starting Jira daily export task for run_flag='{run_flag}' at {start_time.isoformat()}")

    db_conn_pool = db_utils.get_connection_pool()
    try:
        jira = get_jira_client()
        jql_query = jira_processor.build_daily_jql(db_conn_pool)
        
        # --- FIX: Determine required fields before fetching ---
        fields_to_fetch = jira_processor.get_required_field_list(jira)
        all_issues = jira_processor.fetch_all_issues(jira, jql_query, fields_to_fetch)

        if not all_issues:
            logger.info("No daily issues found to process.")
            # Still log the run even if no issues are found
            end_time = datetime.now()
            db_utils.update_run_log(db_conn_pool, start_time, end_time, run_flag)
            logger.info(f"Jira daily export task finished. Duration: {end_time - start_time}")
            return

        jira_processor.process_and_load_issues(db_conn_pool, all_issues, run_flag, jira)
        
    except Exception as e:
        logger.error(f"An error occurred during Jira daily export task: {e}")
    finally:
        end_time = datetime.now()
        if db_conn_pool:
             db_utils.update_run_log(db_conn_pool, start_time, end_time, run_flag)
        logger.info(f"Jira daily export task finished. Duration: {end_time - start_time}")

def run_new_release_export_task():
    """Worker task for the new, targeted 'release' data sync."""
    start_time = datetime.now()
    logger.info(f"Starting NEW targeted release export task at {start_time.isoformat()}")
    db_conn_pool = db_utils.get_connection_pool()
    try:
        jira = get_jira_client()
        # This single function now orchestrates the entire new release logic
        jira_processor.process_release_data(jira, db_conn_pool)
    except Exception as e:
        logger.error(f"An error occurred during the new release export task: {e}")
    finally:
        end_time = datetime.now()
        # Log this run with the 'RELEASE' type for the next run's time check
        db_utils.update_run_log(db_conn_pool, start_time, end_time, 'RELEASE')
        logger.info(f"NEW targeted release export task finished. Duration: {end_time - start_time}")


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
    except Exception as e:
        logger.error(f"An error occurred during investment trends generation: {e}")

def check_if_release_run_is_due():
    logger.info("Checking if a release run is due...")
    db_conn_pool = db_utils.get_connection_pool()
    return db_utils.release_run_check(db_conn_pool)

def run_jira_icebox_task():
    start_time = datetime.now()
    logger.info(f"Starting Jira icebox task at {start_time.isoformat()}...")
    try:
        if jira_automation_app:
            jira_automation_app.main()
        else:
            logger.error("The 'jira_automation.jira_icebox' module is not available.")
    except Exception as e:
        logger.error(f"An error occurred during the Jira icebox task: {e}")
    finally:
        end_time = datetime.now()
        logger.info(f"Jira icebox task finished. Duration: {end_time - start_time}")

def run_daily_pushes_task():
    start_time = datetime.now()
    logger.info(f"Starting daily push report task at {start_time.isoformat()}...")
    try:
        if daily_pushes:
            daily_pushes.main()
        else:
            logger.error("The 'jira_automation.daily_pushes' module is not available.")
    except Exception as e:
        logger.error(f"An error occurred during the daily push report task: {e}")
    finally:
        end_time = datetime.now()
        logger.info(f"Daily push report task finished. Duration: {end_time - start_time}")

def run_rca_subtask_creation_task():
    start_time = datetime.now()
    logger.info(f"Starting RCA sub-task creation task at {start_time.isoformat()}...")
    try:
        create_rca_subtasks.main()
    except Exception as e:
        logger.error(f"An error occurred during the RCA sub-task creation task: {e}")
    finally:
        end_time = datetime.now()
        logger.info(f"RCA sub-task creation task finished. Duration: {end_time - start_time}")

def run_derive_platform_version_task():
    start_time = datetime.now()
    logger.info(f"Starting platform version derivation task at {start_time.isoformat()}...")
    try:
        derive_platform_version.main()
    except Exception as e:
        logger.error(f"An error occurred during the platform version derivation task: {e}")
    finally:
        end_time = datetime.now()
        logger.info(f"Platform version derivation task finished. Duration: {end_time - start_time}")

def run_data_quality_report_task():
    start_time = datetime.now()
    logger.info("Starting data quality report task...")
    try:
        run_derive_platform_version_task()
        data_quality_report.main()
    except Exception as e:
        logger.error(f"An error occurred during the data quality report generation: {e}")
    finally:
        end_time = datetime.now()
        logger.info(f"Data quality report task finished. Duration: {end_time - start_time}")

def run_customer_analysis_task():
    start_time = datetime.now()
    logger.info(f"Starting customer analysis task at {start_time.isoformat()}...")
    try:
        customer_analysis.main()
    except Exception as e:
        logger.error(f"An error occurred during the customer analysis task: {e}")
    finally:
        end_time = datetime.now()
        logger.info(f"Customer analysis task finished. Duration: {end_time - start_time}")

def run_ldap_report_task():
    start_time = datetime.now()
    logger.info(f"Starting LDAP manager report task at {start_time.isoformat()}...")
    try:
        ldap_manager_report.main()
    except Exception as e:
        logger.error(f"An error occurred during the LDAP manager report task: {e}")
    finally:
        end_time = datetime.now()
        logger.info(f"LDAP manager report task finished. Duration: {end_time - start_time}")

def run_bug_snapshot_collection_task():
    logger.info("Starting bug snapshot collection task...")
    try:
        collect_bug_snapshots.main()
    except Exception as e:
        logger.error(f"An error occurred during snapshot collection: {e}")

def run_bug_chart_generation_task():
    logger.info("Starting bug chart generation task...")
    try:
        logger.info("Running snapshot collection first to ensure data is fresh...")
        collect_bug_snapshots.main()
        logger.info("Now generating charts...")
        generate_bug_charts.main()
    except Exception as e:
        logger.error(f"An error occurred during chart generation: {e}")

def task_compdiv_burndown_all():
    # Optional: advisory lock to avoid overlaps
    # from util.locks import advisory_lock
    # with advisory_lock(3001):
    return run_for_all_compdiv_epics(run_dt=date.today())