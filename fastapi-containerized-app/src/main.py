from fastapi import FastAPI
from datetime import datetime
from app.daily_jira_data import (setup_jira_client, fetch_issues, process_and_export_issues,
                             update_postgres_logs, build_jql)
import asyncio
import sys

# Create the FastAPI app
app = FastAPI()

@app.get("/")
async def read_root():
    return {"message": "Welcome to the FastAPI application!"}

@app.get("/daily")
async def daily():
    start_date = datetime.now()
    formatted_start_date = start_date.strftime('%d-%m-%y %H:%M:%S')
    postgres_log_start_date = formatted_start_date
    print("Starting at....", formatted_start_date)

    jira = setup_jira_client()
    if jira is None:
        print("Failed to initialize JIRA client. Ensure your configuration and credentials are correct.")
        sys.exit(1)  # Exit the program if JIRA client setup fails
    print("JIRA client initialized successfully.")

    all_issues = fetch_issues(jira, build_jql())

    process_and_export_issues(all_issues)

    end_date = datetime.now()
    formatted_end_date = end_date.strftime('%d-%m-%y %H:%M:%S')
    postgres_log_end_date = formatted_end_date
    update_postgres_logs(postgres_log_start_date, postgres_log_end_date)
    print("Completed at...", formatted_end_date)
    return 

if __name__ == "__main__":
    asyncio.run(daily())