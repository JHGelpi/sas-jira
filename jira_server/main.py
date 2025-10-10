# jira_server/main.py
"""
Jira Data Processing API

A FastAPI application that provides endpoints for triggering various Jira data
processing jobs, analytics, and automation tasks.
"""

import os
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

# --- Import and call the logging setup function FIRST ---
from logging_config import setup_logging
setup_logging()

# Now get our standardized logger
from logging_utils import get_logger

logger = get_logger(__name__)

# Import the task functions
from tasks import (
    run_jira_export_task,
    run_initiative_analysis_task,
    run_investment_trends_task,
    check_if_release_run_is_due,
    run_jira_icebox_task,
    run_daily_pushes_task,
    run_rca_subtask_creation_task,
    run_data_quality_report_task,
    run_customer_analysis_task,
    run_derive_platform_version_task,
    run_ldap_report_task,
    run_bug_snapshot_collection_task,
    run_bug_chart_generation_task,
    run_new_release_export_task,
    task_compdiv_burndown_all
)

from jira_automation.compdiv_burndown import build_plot_html

# Load environment variables from .env file
load_dotenv()

# Initialize FastAPI application
app = FastAPI(
    title="Jira Data Processing API",
    description="An API to trigger and manage Jira data processing jobs.",
    version="2.4.0"
)

logger.success("FastAPI application initialized successfully")
logger.info("API Title: Jira Data Processing API")
logger.info("API Version: 2.4.0")


@app.on_event("startup")
async def startup_event():
    """Runs when the application starts up."""
    logger.start("FastAPI application starting up")
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    logger.info(f"Jira URL: {os.getenv('JIRA_URL', 'Not configured')}")
    logger.success("Application startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Runs when the application shuts down."""
    logger.info("FastAPI application shutting down")


@app.get("/", summary="Root Welcome Message")
async def read_root():
    """Provides a simple welcome message."""
    logger.info("Root endpoint accessed")
    return {
        "message": "Welcome to the Jira Data Processing API",
        "version": "2.4.0",
        "docs": "/docs",
        "status": "running"
    }


@app.get("/health", summary="Health Check")
async def health_check():
    """Health check endpoint for monitoring."""
    logger.debug("Health check endpoint accessed")
    return {
        "status": "healthy",
        "service": "Jira Data Processing API",
        "version": "2.4.0"
    }


@app.post("/jobs/daily", status_code=202, summary="Trigger Daily Jira Data Sync")
async def trigger_daily_job(background_tasks: BackgroundTasks):
    """
    Starts the daily job to sync Jira issues updated since the last run.
    This also checks if a post-release analysis is due and triggers it.
    """
    logger.info("Daily job endpoint triggered via API")
    logger.processing("Scheduling daily sync background task")
    
    background_tasks.add_task(run_jira_export_task, 'daily')

    if check_if_release_run_is_due():
        logger.info("Release run is due. Scheduling post-release analysis tasks")
        
        background_tasks.add_task(run_new_release_export_task)
        background_tasks.add_task(run_initiative_analysis_task)
        background_tasks.add_task(run_investment_trends_task)
        
        logger.success("Daily sync job and post-release analysis scheduled")
        return {
            "message": "Daily sync job started. Post-release analysis has also been triggered.",
            "status": "scheduled",
            "tasks": ["daily_sync", "release_analysis"]
        }

    logger.success("Daily sync job scheduled")
    return {
        "message": "Daily Jira sync job has been started in the background.",
        "status": "scheduled",
        "tasks": ["daily_sync"]
    }


@app.post("/jobs/release", status_code=202, summary="Manually Trigger a Full Release Analysis")
async def trigger_release_job(background_tasks: BackgroundTasks):
    """
    Manually starts a full post-release analysis using the new logic.
    """
    logger.info("Manual release job endpoint triggered via API")
    logger.processing("Scheduling release analysis background tasks")
    
    background_tasks.add_task(run_new_release_export_task)
    background_tasks.add_task(run_initiative_analysis_task)
    background_tasks.add_task(run_investment_trends_task)
    
    logger.success("Release analysis jobs scheduled")
    return {
        "message": "Release analysis job has been started in the background.",
        "status": "scheduled",
        "tasks": ["release_export", "initiative_analysis", "investment_trends"]
    }


@app.post("/jobs/jiraicebox", status_code=202, summary="Trigger Jira Icebox Updates")
async def trigger_jira_icebox_job(background_tasks: BackgroundTasks):
    """
    Starts the Jira icebox update job. This job runs in the background.
    """
    logger.info("Jira icebox job endpoint triggered via API")
    logger.processing("Scheduling Jira icebox background task")
    
    background_tasks.add_task(run_jira_icebox_task)
    
    logger.success("Jira icebox job scheduled")
    return {
        "message": "Jira icebox update job has been started in the background.",
        "status": "scheduled",
        "tasks": ["jira_icebox"]
    }


@app.post("/jobs/daily-pushes", status_code=202, summary="Generate Daily Push Report")
async def trigger_daily_pushes_job(background_tasks: BackgroundTasks):
    """
    Starts a job to find all tickets with pushes in the last 24 hours
    and generates a CSV report.
    """
    logger.info("Daily push report job endpoint triggered via API")
    logger.processing("Scheduling daily push report background task")
    
    background_tasks.add_task(run_daily_pushes_task)
    
    logger.success("Daily push report job scheduled")
    return {
        "message": "Daily push report job has been started in the background.",
        "status": "scheduled",
        "tasks": ["daily_pushes"]
    }


@app.post("/jobs/create-rca-subtasks", status_code=202, summary="Create RCA Sub-tasks for Critical Bugs")
async def trigger_rca_subtask_job(background_tasks: BackgroundTasks):
    """
    Starts a job to find critical bugs from CRP and create an RCA sub-task
    if one does not already exist.
    """
    logger.info("RCA sub-task job endpoint triggered via API")
    logger.processing("Scheduling RCA sub-task creation background task")
    
    background_tasks.add_task(run_rca_subtask_creation_task)
    
    logger.success("RCA sub-task creation job scheduled")
    return {
        "message": "RCA sub-task creation job has been started in the background.",
        "status": "scheduled",
        "tasks": ["rca_subtasks"]
    }


@app.post("/jobs/data-quality-report", status_code=202, summary="Generate Data Quality Reports")
async def trigger_data_quality_report_job(background_tasks: BackgroundTasks):
    """
    Starts a job to run multiple JQL queries and generate CSV reports
    for tickets with missing data.
    """
    logger.info("Data quality report job endpoint triggered via API")
    logger.processing("Scheduling data quality report background task")
    
    background_tasks.add_task(run_data_quality_report_task)
    
    logger.success("Data quality report job scheduled")
    return {
        "message": "Data quality report job has been started in the background.",
        "status": "scheduled",
        "tasks": ["data_quality_report"]
    }


@app.post("/jobs/customer-analysis", status_code=202, summary="Analyze and Update Customer Bugs")
async def trigger_customer_analysis_job(background_tasks: BackgroundTasks):
    """
    Starts a job to find open bugs with customer labels, update the
    Origin field if necessary, and generate a CSV report.
    """
    logger.info("Customer analysis job endpoint triggered via API")
    logger.processing("Scheduling customer analysis background task")
    
    background_tasks.add_task(run_customer_analysis_task)
    
    logger.success("Customer analysis job scheduled")
    return {
        "message": "Customer analysis job has been started in the background.",
        "status": "scheduled",
        "tasks": ["customer_analysis"]
    }


@app.post("/jobs/derive-platform-version", status_code=202, summary="Derive Platform Version for Bugs")
async def trigger_derive_platform_version_job(background_tasks: BackgroundTasks):
    """
    Starts a job to find bugs where the Platform Version can be derived
    from the Affects Version/s field and updates them.
    """
    logger.info("Platform version derivation job endpoint triggered via API")
    logger.processing("Scheduling platform version derivation background task")
    
    background_tasks.add_task(run_derive_platform_version_task)
    
    logger.success("Platform version derivation job scheduled")
    return {
        "message": "Platform version derivation job has been started in the background.",
        "status": "scheduled",
        "tasks": ["derive_platform_version"]
    }


@app.post("/jobs/ldap-refresh", status_code=202, summary="Refresh LDAP Hierarchy in Database")
async def trigger_ldap_report_job(background_tasks: BackgroundTasks):
    """
    Starts a job to connect to LDAP, find all direct and indirect reports
    for a given list of managers, and sync the data to the database.
    """
    logger.info("LDAP refresh job endpoint triggered via API")
    logger.processing("Scheduling LDAP hierarchy refresh background task")
    
    background_tasks.add_task(run_ldap_report_task)
    
    logger.success("LDAP refresh job scheduled")
    return {
        "message": "LDAP hierarchy refresh job has been started in the background.",
        "status": "scheduled",
        "tasks": ["ldap_refresh"]
    }


@app.post("/jobs/collect-bug-snapshots", status_code=202, summary="Trigger Daily Bug Snapshot Collection")
async def trigger_bug_snapshot_collection(background_tasks: BackgroundTasks):
    """
    Starts the daily job to collect a snapshot of all Jira bugs.
    This should be run daily to build time-series data.
    """
    logger.info("Bug snapshot collection job endpoint triggered via API")
    logger.processing("Scheduling bug snapshot collection background task")
    
    background_tasks.add_task(run_bug_snapshot_collection_task)
    
    logger.success("Bug snapshot collection job scheduled")
    return {
        "message": "Bug snapshot collection job started in the background.",
        "status": "scheduled",
        "tasks": ["bug_snapshots"]
    }


@app.post("/jobs/generate-bug-charts", status_code=202, summary="Generate Bug Trend Charts")
async def trigger_bug_chart_generation(background_tasks: BackgroundTasks):
    """
    Generates the bug trend HTML report from the collected snapshot data.
    """
    logger.info("Bug trend chart generation job endpoint triggered via API")
    logger.processing("Scheduling bug chart generation background task")
    
    background_tasks.add_task(run_bug_chart_generation_task)
    
    logger.success("Bug chart generation job scheduled")
    return {
        "message": "Bug trend chart generation job started in the background.",
        "status": "scheduled",
        "tasks": ["bug_charts"]
    }


@app.post("/jobs/compdiv-burndown", status_code=202, summary="Trigger COMPDIV Burndown for All Epics")
async def trigger_compdiv_burndown(background_tasks: BackgroundTasks):
    """
    Enqueues a background job to run COMPDIV burndown analysis for all epics.
    """
    logger.info("COMPDIV burndown job endpoint triggered via API")
    logger.processing("Scheduling COMPDIV burndown background task")
    
    background_tasks.add_task(task_compdiv_burndown_all)
    
    logger.success("COMPDIV burndown job scheduled")
    return {
        "message": "Enqueued COMPDIV burndown for all epics",
        "status": "scheduled",
        "tasks": ["compdiv_burndown"]
    }


@app.get("/reports/compdiv-burndown/{epic_key}", response_class=HTMLResponse, summary="View COMPDIV Burndown Report")
async def report_compdiv_burndown(epic_key: str):
    """
    Retrieves and displays the burndown chart for a specific COMPDIV epic.
    
    Args:
        epic_key: The Jira epic key (e.g., COMPDIV-123)
    
    Returns:
        HTML page with the burndown chart
    """
    logger.info(f"COMPDIV burndown report requested for epic: {epic_key}")
    
    try:
        html = build_plot_html(epic_key)
        logger.success(f"Generated burndown report for {epic_key}")
        return HTMLResponse(content=html, status_code=200)
    except Exception as e:
        logger.error(f"Failed to generate burndown report for {epic_key}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate burndown report for {epic_key}"
        )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.exception(f"Unhandled exception in {request.url.path}: {exc}")
    return {
        "error": "Internal server error",
        "detail": str(exc),
        "path": str(request.url.path)
    }


if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting Uvicorn server directly (development mode)")
    logger.info("For production, use: uvicorn main:app --host 0.0.0.0 --port 8000")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_config="log_config.yaml"
    )