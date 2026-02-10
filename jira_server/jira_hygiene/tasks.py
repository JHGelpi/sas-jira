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
                             generate_bug_charts, jira_burndown, generate_burndown_dashboard, iris_burndown)
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