import os
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
import logging

# --- Import and call the logging setup function ---
from logging_config import setup_logging
setup_logging()

logger = logging.getLogger(__name__)

# Import the task functions
from tasks import (run_jira_export_task, 
                    run_initiative_analysis_task, 
                    run_investment_trends_task, 
                    check_if_release_run_is_due,
                    run_jira_icebox_task,
                    run_daily_pushes_task,
                    run_daily_pushes_task,
                    run_rca_subtask_creation_task,
                    run_data_quality_report_task,
                    run_customer_analysis_task,
                    run_derive_platform_version_task,
                    run_ldap_report_task,
                    run_bug_snapshot_collection_task,
                    run_bug_chart_generation_task,
                    run_new_release_export_task,
                    task_compdiv_burndown_all)

from jira_automation.compdiv_burndown import (build_plot_html)

# Load environment variables from .env file
load_dotenv()

app = FastAPI(
    title="Jira Data Processing API",
    description="An API to trigger and manage Jira data processing jobs.",
    version="2.3.0"
)

@app.get("/", summary="Root Welcome Message")
async def read_root():
    """Provides a simple welcome message."""
    return {"message": "Welcome to the Jira Data Processing API. Use the /docs endpoint for details."}

@app.post("/jobs/daily", status_code=202, summary="Trigger Daily Jira Data Sync")
async def trigger_daily_job(background_tasks: BackgroundTasks):
    """
    Starts the daily job to sync Jira issues updated since the last run.
    This also checks if a post-release analysis is due and triggers it.
    """
    logger.info("Daily job endpoint triggered. Scheduling background tasks.")
    background_tasks.add_task(run_jira_export_task, 'daily')

    if check_if_release_run_is_due():
        logger.info("Release run is due. Scheduling new post-release analysis tasks.")
        # --- FIX: Call the new, targeted release task ---
        background_tasks.add_task(run_new_release_export_task)
        
        # Chain subsequent tasks that depend on the release data
        background_tasks.add_task(run_initiative_analysis_task)
        background_tasks.add_task(run_investment_trends_task)
        return {"message": "Daily sync job started. Post-release analysis has also been triggered."}

    return {"message": "Daily Jira sync job has been started in the background."}


@app.post("/jobs/release", status_code=202, summary="Manually Trigger a Full Release Analysis")
async def trigger_release_job(background_tasks: BackgroundTasks):
    """
    Manually starts a full post-release analysis using the new logic.
    """
    logger.info("Manual release job endpoint triggered. Scheduling background tasks.")
    # --- FIX: Call the new, targeted release task ---
    background_tasks.add_task(run_new_release_export_task)
    background_tasks.add_task(run_initiative_analysis_task)
    background_tasks.add_task(run_investment_trends_task)
    return {"message": "Release analysis job has been started in the background."}

@app.post("/jobs/jiraicebox", status_code=202, summary="Trigger Jira icebox updates")
async def trigger_jira_icebox_job(background_tasks: BackgroundTasks):
    """
    Starts the Jira icebox update job. This job runs in the background.
    """
    print("Jira icebox job endpoint triggered. Scheduling background tasks.")
    # --- FIX: Call the correct task function ---
    background_tasks.add_task(run_jira_icebox_task)
    return {"message": "Jira icebox update job has been started in the background."}

# --- Endpoint for the daily push report ---
@app.post("/jobs/daily-pushes", status_code=202, summary="Generate Daily Push Report")
async def trigger_daily_pushes_job(background_tasks: BackgroundTasks):
    """
    Starts a job to find all tickets with pushes in the last 24 hours
    and generates a CSV report.
    """
    print("Daily push report job endpoint triggered. Scheduling background task.")
    background_tasks.add_task(run_daily_pushes_task)
    return {"message": "Daily push report job has been started in the background."}
# --- Endpoint for the RCA sub-task creation ---
@app.post("/jobs/create-rca-subtasks", status_code=202, summary="Create RCA Sub-tasks for Critical Bugs")
async def trigger_rca_subtask_job(background_tasks: BackgroundTasks):
    """
    Starts a job to find critical bugs from CRP and create an RCA sub-task
    if one does not already exist.
    """
    print("RCA sub-task job endpoint triggered. Scheduling background task.")
    background_tasks.add_task(run_rca_subtask_creation_task)
    return {"message": "RCA sub-task creation job has been started in the background."}

# --- Endpoint for the data quality report ---
@app.post("/jobs/data-quality-report", status_code=202, summary="Generate Data Quality Reports")
async def trigger_data_quality_report_job(background_tasks: BackgroundTasks):
    """
    Starts a job to run multiple JQL queries and generate CSV reports
    for tickets with missing data.
    """
    print("Data quality report job endpoint triggered. Scheduling background task.")
    background_tasks.add_task(run_data_quality_report_task)
    return {"message": "Data quality report job has been started in the background."}

# --- Endpoint for the customer analysis report ---
@app.post("/jobs/customer-analysis", status_code=202, summary="Analyze and Update Customer Bugs")
async def trigger_customer_analysis_job(background_tasks: BackgroundTasks):
    """
    Starts a job to find open bugs with customer labels, update the
    Origin field if necessary, and generate a CSV report.
    """
    print("Customer analysis job endpoint triggered. Scheduling background task.")
    background_tasks.add_task(run_customer_analysis_task)
    return {"message": "Customer analysis job has been started in the background."}

# --- Endpoint for the platform version derivation ---
@app.post("/jobs/derive-platform-version", status_code=202, summary="Derive Platform Version for Bugs")
async def trigger_derive_platform_version_job(background_tasks: BackgroundTasks):
    """
    Starts a job to find bugs where the Platform Version can be derived
    from the Affects Version/s field and updates them.
    """
    print("Platform version derivation job endpoint triggered. Scheduling background task.")
    background_tasks.add_task(run_derive_platform_version_task)
    return {"message": "Platform version derivation job has been started in the background."}

# --- Endpoint for the LDAP manager report ---
@app.post("/jobs/ldap-refresh", status_code=202, summary="Refresh LDAP Hierarchy in Database")
async def trigger_ldap_report_job(background_tasks: BackgroundTasks):
    """
    Starts a job to connect to LDAP, find all direct and indirect reports
    for a given list of managers, and sync the data to the database.
    """
    print("LDAP refresh job endpoint triggered. Scheduling background task.")
    background_tasks.add_task(run_ldap_report_task)
    return {"message": "LDAP hierarchy refresh job has been started in the background."}

@app.post("/jobs/collect-bug-snapshots", status_code=202, summary="Trigger Daily Bug Snapshot Collection")
def trigger_bug_snapshot_collection(background_tasks: BackgroundTasks):
    """
    Starts the daily job to collect a snapshot of all Jira bugs.
    This should be run daily to build time-series data.
    """
    background_tasks.add_task(run_bug_snapshot_collection_task)
    return {"message": "Bug snapshot collection job started in the background."}

@app.post("/jobs/generate-bug-charts", status_code=202, summary="Generate Bug Trend Charts")
def trigger_bug_chart_generation(background_tasks: BackgroundTasks):
    """
    Generates the bug trend HTML report from the collected snapshot data.
    """
    background_tasks.add_task(run_bug_chart_generation_task)
    return {"message": "Bug trend chart generation job started in the background."}


@app.post("/jobs/compdiv-burndown", status_code=202)
def trigger_compdiv_burndown(background_tasks: BackgroundTasks):
    background_tasks.add_task(task_compdiv_burndown_all)
    return {"message": "Enqueued COMPDIV burndown for all epics"}

@app.get("/reports/compdiv-burndown/{epic_key}", response_class=HTMLResponse)
def report_compdiv_burndown(epic_key: str):
    html = build_plot_html(epic_key)
    return HTMLResponse(content=html, status_code=200)
