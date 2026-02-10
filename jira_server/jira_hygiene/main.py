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
    run_jira_icebox_task
    #run_rca_subtask_creation_task,
    #run_data_quality_report_task,
    #run_derive_platform_version_task
)

from jira_automation.jira_burndown import build_plot_html

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