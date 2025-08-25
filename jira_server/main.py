import os
from fastapi import FastAPI, BackgroundTasks, HTTPException
from dotenv import load_dotenv

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
                    run_derive_platform_version_task)

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
    This job runs in the background.
    """
    print("Daily job endpoint triggered. Scheduling background tasks.")
    background_tasks.add_task(run_jira_export_task, 'daily')

    # The daily job will check if a post-release analysis is needed
    if check_if_release_run_is_due():
        print("Release run is due. Scheduling post-release analysis tasks.")
        background_tasks.add_task(run_jira_export_task, 'release')
        # Chain subsequent tasks to run after the release data is processed
        background_tasks.add_task(run_initiative_analysis_task)
        background_tasks.add_task(run_investment_trends_task)
        return {"message": "Daily sync job started. Post-release analysis has also been triggered."}

    return {"message": "Daily Jira sync job has been started in the background."}


@app.post("/jobs/release", status_code=202, summary="Manually Trigger a Full Release Analysis")
async def trigger_release_job(background_tasks: BackgroundTasks):
    """
    Manually starts a full post-release analysis. This includes fetching
    release-specific Jira issues, updating initiative data, and generating
    investment trend charts. This job runs in the background.
    """
    print("Manual release job endpoint triggered. Scheduling background tasks.")
    background_tasks.add_task(run_jira_export_task, 'release')
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
