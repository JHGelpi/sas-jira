# jira_server/tasks.py
"""
Background task orchestration.

This module contains all the task functions that are called by the FastAPI
endpoints as background jobs.
"""

import os
from datetime import datetime, date
from jira import JIRA
from jira_data_analysis import (jira_processor, initiative_children, investment_trends, db_utils)
from jira_automation import (create_rca_subtasks, data_quality_report, customer_analysis,
                             derive_platform_version, ldap_manager_report, collect_bug_snapshots,
                             generate_bug_charts, compdiv_burndown, generate_burndown_dashboard, iris_burndown)
from logging_utils import get_logger, log_section_header

logger = get_logger(__name__)

# Use robust import structure for each module
try:
    from jira_automation import jira_icebox as jira_automation_app
except ImportError:
    jira_automation_app = None
    logger.warning("Could not import jira_automation.jira_icebox. The icebox task will not be available")

try:
    from jira_automation import ticket_aging
except ImportError:
    ticket_aging = None
    logger.warning("Could not import 'jira_automation.ticket_aging'. The ticket aging job will be unavailable")

try:
    from jira_automation import daily_pushes
except ImportError:
    daily_pushes = None
    logger.warning("Could not import 'jira_automation.daily_pushes'. The daily pushes job will be unavailable")


def get_jira_client():
    """Initializes and returns a JIRA client."""
    try:
        logger.connecting("Initializing Jira client")
        jira = JIRA(
            server=os.getenv('JIRA_URL'),
            token_auth=os.getenv('JIRA_TOKEN')
        )
        logger.success("Jira client initialized")
        return jira
    except Exception as e:
        logger.error(f"Failed to initialize Jira client: {e}")
        return None


def run_jira_export_task(run_flag: str):
    """The main worker task for the 'daily' data sync."""
    log_section_header(logger, f"JIRA DAILY EXPORT ({run_flag.upper()})")

    start_time = datetime.now()
    logger.start(f"Starting Jira daily export task for run_flag='{run_flag}'")

    db_conn_pool = db_utils.get_connection_pool()
    try:
        jira = get_jira_client()
        if not jira:
            logger.error("Cannot proceed without Jira client")
            return

        jql_query = jira_processor.build_daily_jql(db_conn_pool)

        fields_to_fetch = jira_processor.get_required_field_list(jira)
        all_issues = jira_processor.fetch_all_issues(jira, jql_query, fields_to_fetch)

        if not all_issues:
            logger.info("No daily issues found to process")
            end_time = datetime.now()
            db_utils.update_run_log(db_conn_pool, start_time, end_time, run_flag)
            duration = end_time - start_time
            logger.complete(f"Jira daily export task finished (Duration: {duration})")
            return

        jira_processor.process_and_load_issues(db_conn_pool, all_issues, run_flag, jira)

        # Close completed initiatives daily (both IRIS and COMPDIV)
        # *** DATA SAFETY ***
        # This ONLY updates tbl_initiative_issue_keys metadata (eff_end_date, active_flag).
        # Burndown data tables (tbl_compdiv_burndown, tbl_iris_burndown) are NEVER modified.
        logger.processing("Checking for completed initiatives to close")
        try:
            initiative_children.close_completed_initiatives(jira, db_conn_pool, initiative_type=None)
            logger.success("Completed initiative closure check")
        except Exception as e:
            logger.error(f"Failed to close completed initiatives: {e}")

    except Exception as e:
        logger.exception(f"An error occurred during Jira daily export task: {e}")
    finally:
        end_time = datetime.now()
        if db_conn_pool:
             db_utils.update_run_log(db_conn_pool, start_time, end_time, run_flag)
        duration = end_time - start_time
        logger.complete(f"Jira daily export task finished (Duration: {duration})")


def run_new_release_export_task():
    """Worker task for the new, targeted 'release' data sync."""
    log_section_header(logger, "RELEASE EXPORT")
    
    start_time = datetime.now()
    logger.start("Starting targeted release export task")
    
    db_conn_pool = db_utils.get_connection_pool()
    try:
        jira = get_jira_client()
        if not jira:
            logger.error("Cannot proceed without Jira client")
            return
            
        jira_processor.process_release_data(jira, db_conn_pool)
        
    except Exception as e:
        logger.exception(f"An error occurred during the release export task: {e}")
    finally:
        end_time = datetime.now()
        db_utils.update_run_log(db_conn_pool, start_time, end_time, 'RELEASE')
        duration = end_time - start_time
        logger.complete(f"Release export task finished (Duration: {duration})")


def run_initiative_analysis_task():
    """Runs the initiative children analysis."""
    log_section_header(logger, "INITIATIVE ANALYSIS")
    
    logger.start("Starting initiative analysis task")
    try:
        initiative_children.main()
        logger.complete("Initiative analysis task completed successfully")
    except Exception as e:
        logger.exception(f"An error occurred during initiative analysis: {e}")


def run_investment_trends_task():
    """Runs the investment trends generation."""
    log_section_header(logger, "INVESTMENT TRENDS")
    
    logger.start("Starting investment trends task")
    try:
        investment_trends.main()
        logger.complete("Investment trends task completed successfully")
    except Exception as e:
        logger.exception(f"An error occurred during investment trends generation: {e}")


def check_if_release_run_is_due():
    """Checks if a release run is due."""
    logger.info("Checking if a release run is due")
    db_conn_pool = db_utils.get_connection_pool()
    is_due = db_utils.release_run_check(db_conn_pool)
    
    if is_due:
        logger.info("Release run IS due")
    else:
        logger.info("Release run is NOT due")
    
    return is_due


def run_jira_icebox_task():
    """Runs the Jira icebox automation task."""
    log_section_header(logger, "JIRA ICEBOX")
    
    start_time = datetime.now()
    logger.start("Starting Jira icebox task")
    
    try:
        if jira_automation_app:
            jira_automation_app.main()
        else:
            logger.error("The 'jira_automation.jira_icebox' module is not available")
    except Exception as e:
        logger.exception(f"An error occurred during the Jira icebox task: {e}")
    finally:
        end_time = datetime.now()
        duration = end_time - start_time
        logger.complete(f"Jira icebox task finished (Duration: {duration})")


def run_daily_pushes_task():
    """Runs the daily push report generation task."""
    log_section_header(logger, "DAILY PUSH REPORT")
    
    start_time = datetime.now()
    logger.start("Starting daily push report task")
    
    try:
        if daily_pushes:
            daily_pushes.main()
        else:
            logger.error("The 'jira_automation.daily_pushes' module is not available")
    except Exception as e:
        logger.exception(f"An error occurred during the daily push report task: {e}")
    finally:
        end_time = datetime.now()
        duration = end_time - start_time
        logger.complete(f"Daily push report task finished (Duration: {duration})")


def run_rca_subtask_creation_task():
    """Runs the RCA sub-task creation task."""
    log_section_header(logger, "RCA SUBTASK CREATION")
    
    start_time = datetime.now()
    logger.start("Starting RCA sub-task creation task")
    
    try:
        create_rca_subtasks.main()
    except Exception as e:
        logger.exception(f"An error occurred during the RCA sub-task creation task: {e}")
    finally:
        end_time = datetime.now()
        duration = end_time - start_time
        logger.complete(f"RCA sub-task creation task finished (Duration: {duration})")


def run_derive_platform_version_task():
    """Runs the platform version derivation task."""
    log_section_header(logger, "PLATFORM VERSION DERIVATION")
    
    start_time = datetime.now()
    logger.start("Starting platform version derivation task")
    
    try:
        derive_platform_version.main()
    except Exception as e:
        logger.exception(f"An error occurred during the platform version derivation task: {e}")
    finally:
        end_time = datetime.now()
        duration = end_time - start_time
        logger.complete(f"Platform version derivation task finished (Duration: {duration})")


def run_data_quality_report_task():
    """Runs the data quality report generation task."""
    log_section_header(logger, "DATA QUALITY REPORT")
    
    start_time = datetime.now()
    logger.start("Starting data quality report task")
    
    try:
        run_derive_platform_version_task()
        data_quality_report.main()
    except Exception as e:
        logger.exception(f"An error occurred during the data quality report generation: {e}")
    finally:
        end_time = datetime.now()
        duration = end_time - start_time
        logger.complete(f"Data quality report task finished (Duration: {duration})")


def run_customer_analysis_task():
    """Runs the customer analysis task."""
    log_section_header(logger, "CUSTOMER ANALYSIS")
    
    start_time = datetime.now()
    logger.start("Starting customer analysis task")
    
    try:
        customer_analysis.main()
    except Exception as e:
        logger.exception(f"An error occurred during the customer analysis task: {e}")
    finally:
        end_time = datetime.now()
        duration = end_time - start_time
        logger.complete(f"Customer analysis task finished (Duration: {duration})")


def run_ldap_report_task():
    """Runs the LDAP manager report task."""
    log_section_header(logger, "LDAP MANAGER REPORT")
    
    start_time = datetime.now()
    logger.start("Starting LDAP manager report task")
    
    try:
        ldap_manager_report.main()
    except Exception as e:
        logger.exception(f"An error occurred during the LDAP manager report task: {e}")
    finally:
        end_time = datetime.now()
        duration = end_time - start_time
        logger.complete(f"LDAP manager report task finished (Duration: {duration})")


def run_bug_snapshot_collection_task():
    """Runs the bug snapshot collection task."""
    log_section_header(logger, "BUG SNAPSHOT COLLECTION")
    
    logger.start("Starting bug snapshot collection task")
    try:
        collect_bug_snapshots.main()
        logger.complete("Bug snapshot collection completed successfully")
    except Exception as e:
        logger.exception(f"An error occurred during snapshot collection: {e}")


def run_bug_chart_generation_task():
    """Runs the bug chart generation task."""
    log_section_header(logger, "BUG CHART GENERATION")
    
    logger.start("Starting bug chart generation task")
    try:
        logger.info("Running snapshot collection first to ensure data is fresh")
        collect_bug_snapshots.main()
        logger.info("Now generating charts")
        generate_bug_charts.main()
        logger.complete("Bug chart generation completed successfully")
    except Exception as e:
        logger.exception(f"An error occurred during chart generation: {e}")


def task_compdiv_burndown_all():
    """Runs the COMPDIV burndown for all epics."""
    log_section_header(logger, "COMPDIV BURNDOWN")

    logger.start("Starting COMPDIV burndown for all epics")
    try:
        results = compdiv_burndown.run_for_all_compdiv_epics(run_dt=date.today())
        logger.complete(f"COMPDIV burndown completed for {len(results)} epics")
        return results
    except Exception as e:
        logger.exception(f"An error occurred during COMPDIV burndown: {e}")
        return {}


def run_burndown_dashboard_generation_task():
    """Generates the burndown dashboard from existing HTML files."""
    log_section_header(logger, "BURNDOWN DASHBOARD GENERATION")

    logger.start("Starting burndown dashboard generation task")
    try:
        generate_burndown_dashboard.main()
        logger.complete("Burndown dashboard generation completed successfully")
    except Exception as e:
        logger.exception(f"An error occurred during dashboard generation: {e}")


def task_iris_burndown_all():
    """Runs the IRIS burndown for all active IRIS epics."""
    log_section_header(logger, "IRIS BURNDOWN")

    logger.start("Starting IRIS burndown for all active IRIS epics")
    try:
        results = iris_burndown.run_for_all_iris_epics(run_dt=date.today())
        logger.complete(f"IRIS burndown completed for {len(results)} epics")
        return results
    except Exception as e:
        logger.exception(f"An error occurred during IRIS burndown: {e}")
        return {}