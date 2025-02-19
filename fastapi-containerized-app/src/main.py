from fastapi import FastAPI
from datetime import datetime
from app.daily_jira_data import (setup_jira_client, fetch_issues, process_and_export_issues,
                             update_postgres_logs, build_jql)
import asyncio
import sys
#from app.api.routes import router as api_router
#from app.db import models
#from app.db.database import engine
#from fastapi.middleware.cors import CORSMiddleware

# Create the FastAPI app
app = FastAPI()

# Configure CORS
'''app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this as needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the API router
app.include_router(api_router)

# Create the database tables
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)'''

@app.get("/")
async def read_root():
    return {"message": "Welcome to the FastAPI application!"}

@app.get("/daily")
async def daily():
    start_date = datetime.now()
    formatted_start_date = start_date.strftime('%d-%m-%y %H:%M:%S')
    postgres_log_start_date = formatted_start_date
    print("Starting at....", formatted_start_date)
    #config_data = get_config_data()
    #print("Configuration loaded successfully.")
    jira = setup_jira_client()
    if jira is None:
        print("Failed to initialize JIRA client. Ensure your configuration and credentials are correct.")
        sys.exit(1)  # Exit the program if JIRA client setup fails
    print("JIRA client initialized successfully.")
    
    #if config_data['sprints'] == 'current':
    all_issues = fetch_issues(jira, build_jql())
    #else:
    #    all_issues = fetch_issues(jira, build_jql_completed())
    #print(f"Fetched {len(all_issues)} issues.")
    process_and_export_issues(all_issues)
    
    #print ("Looking for new initiatives...")
    #compdiv_initiatives()
    #print ("Finished updating initiatives...")

    end_date = datetime.now()
    formatted_end_date = end_date.strftime('%d-%m-%y %H:%M:%S')
    postgres_log_end_date = formatted_end_date
    update_postgres_logs(postgres_log_start_date, postgres_log_end_date)
    print("Completed at...", formatted_end_date)
    return 

if __name__ == "__main__":
    asyncio.run(daily())