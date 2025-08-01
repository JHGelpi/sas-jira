import os
from fastapi import FastAPI, BackgroundTasks, HTTPException
from dotenv import load_dotenv

# Import the task functions
from jira_data_analysis.tasks import run_jira_export_task, run_initiative_analysis_task, run_investment_trends_task, check_if_release_run_is_due

# Load environment variables from .env file
load_dotenv()

app = FastAPI(
    title="Jira Data Processing API",
    description="An API to trigger and manage Jira data processing jobs.",
    version="2.0.0"
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

# To run the app, use the 'run_app.sh' script or execute this command in your terminal:
# uvicorn main:app --reload