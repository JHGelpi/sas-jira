from fastapi import FastAPI
from datetime import datetime
from app.daily_jira_data import (setup_jira_client, fetch_issues, process_and_export_issues,
                             update_postgres_logs, build_jql, create_connection)
import asyncio
import sys

# Create the FastAPI app
app = FastAPI()

@app.get("/")
async def read_root():
    return {"message": "Welcome to the FastAPI application!"}

@app.get("/release")
async def release():
    #This will be scheduled to run upon the completion of a release.
    #I will need to reference a table that records the release date for our monthly stables
    #That will then inform when this code is executed.  I expect it will be triggered by
    #the "/daily" endpoint.
    run_flag = 'release'
    start_date = datetime.now()
    formatted_start_date = start_date.strftime('%d-%m-%y %H:%M:%S')
    postgres_log_start_date = formatted_start_date
    print("Starting at....", formatted_start_date)

    jira = setup_jira_client()
    if jira is None:
        print("Failed to initialize JIRA client. Ensure your configuration and credentials are correct.")
        sys.exit(1)  # Exit the program if JIRA client setup fails
    print("JIRA client initialized successfully.")

    all_issues = fetch_issues(jira, build_jql(run_flag))

    process_and_export_issues(all_issues, run_flag)

    end_date = datetime.now()
    formatted_end_date = end_date.strftime('%d-%m-%y %H:%M:%S')
    postgres_log_end_date = formatted_end_date
    update_postgres_logs(postgres_log_start_date, postgres_log_end_date, run_flag)
    print("Completed at...", formatted_end_date)

@app.get("/daily")
async def daily():
    run_flag = 'daily'
    start_date = datetime.now()
    formatted_start_date = start_date.strftime('%d-%m-%y %H:%M:%S')
    postgres_log_start_date = formatted_start_date
    print("Starting at....", formatted_start_date)

    jira = setup_jira_client()
    if jira is None:
        print("Failed to initialize JIRA client. Ensure your configuration and credentials are correct.")
        sys.exit(1)  # Exit the program if JIRA client setup fails
    print("JIRA client initialized successfully.")

    all_issues = fetch_issues(jira, build_jql(run_flag))

    process_and_export_issues(all_issues, run_flag)

    end_date = datetime.now()
    formatted_end_date = end_date.strftime('%d-%m-%y %H:%M:%S')
    postgres_log_end_date = formatted_end_date
    update_postgres_logs(postgres_log_start_date, postgres_log_end_date, run_flag)
    print("Completed at...", formatted_end_date)

    # Check to see if the release run needs to be triggered
    conn = create_connection()
    cursor = conn.cursor()
    sql_query = """
            select max(a.release_date) from tbl_jira_releases a where a.release_date <= current_date;
        """
    
    cursor.execute(sql_query)
    target_release_date = cursor.fetchone()[0]
    
    sql_query = """
            select max(a.last_run_date) from tbl_jira_logs a where a.run_flag = 'daily';
        """
    cursor.execute(sql_query)
    last_run_date = cursor.fetchone()[0]
    
    # If the release date is today and the release run has not been triggered, then trigger it
    # If the last run date is AFTER the target_release_date, then trigger the release run
    if last_run_date is None or last_run_date >= target_release_date:
        print("Triggering release run...")
        await release()

    return 

if __name__ == "__main__":
    #asyncio.run(daily())
    asyncio.run(release())