Jira Automation & Reporting Server

This project provides a FastAPI-based server to automate various Jira workflows, data analysis tasks, and reporting. It is designed to be run locally on a macOS machine, with jobs triggered via API endpoints and scheduled with cron.
Project Structure

jira_server/
├── .env                    # Main configuration file for all secrets and settings
├── main.py                 # FastAPI server definition and API endpoints
├── run_app.sh              # Script to set up the environment and run the server
├── run_task.py             # Helper script for running tasks directly via cron
├── requirements.txt        # Python package dependencies
├── venv/                   # Python virtual environment (ignored by Git)
├── logs/                   # Directory for server and cron job logs
├── reports/                # Output directory for generated CSV and HTML reports
│   └── index.html          # Homepage to display the latest push report
├── helper_files/
│   └── customer_support_lvls.json # Configuration for customer analysis
├── jira_data_analysis/     # Package for data ETL and analysis scripts
│   ├── __init__.py
│   ├── tasks.py            # Core background task definitions
│   ├── db_utils.py         # Database connection and utility functions
│   ├── initiative_children.py # Logic for initiative-to-child issue mapping
│   └── ...
└── jira_automation/        # Package for scripts that perform actions in Jira
    ├── __init__.py
    ├── app.py              # Icebox automation logic
    ├── customer_analysis.py # Customer bug monitoring and reporting
    ├── create_rca_subtasks.py # RCA sub-task creation for critical bugs
    └── ...

Setup and Installation
Prerequisites

    Python 3.10+

    A running PostgreSQL database instance.

1. Set Up the Virtual Environment

It is highly recommended to use a Python virtual environment to manage dependencies. The run_app.sh script will do this for you automatically. The first time you run it, it will create a venv directory and install all required packages from requirements.txt.
2. Configure Environment Variables

All configuration is managed through a single .env file in the jira_server/ root directory. Create this file by copying .env.example (if one exists) or by creating it from scratch.

Required Variables:

# Jira API Credentials
JIRA_URL="[https://your-jira-instance.com](https://your-jira-instance.com)"
JIRA_TOKEN="your_personal_access_token"

# Database Connection
DATABASE_URL="postgresql://user:password@host:port/dbname"

# General Configuration
JIRA_PROJECTS="PROJ1,PROJ2,PROJ3"
JIRA_REPORT_DIR="./reports"
HOMEPAGE_REPORTS_DIR="/path/to/your/homepage/reports/"

# Initiative Analysis
JIRA_INITIATIVE_JQL="project = COMPDIV AND type = Epic AND labels in (label1, label2)"
JIRA_IRIS_LABELS="iris-label-1,iris-label-2"

# Ticket Aging Report
JIRA_AGING_PROJECT="COMPDIV"
JIRA_AGING_DAYS="30"
JIRA_AGING_STATUS_CATEGORY='"In Progress"'

# Daily Push Report
JIRA_PUSH_REPORT_DAYS="7"

# RCA Sub-task Creation
JIRA_RCA_ORIGIN_FIELD_NAME="Origin"
JIRA_CREATED_DATE="2025-01-01"

# Data Quality Report
JQL_MISSING_FIXVER="project in (COMPDIV) AND fixVersion is EMPTY"
JQL_MISSING_ORIGIN="project in (COMPDIV) AND Origin is EMPTY"
# ... (and other JQL variables) ...

# Customer Analysis
JIRA_CUSTOMER_JSON_PATH="helper_files/customer_support_lvls.json"

Running the Server

To start the application, run the provided shell script from the jira_server directory:

./run_app.sh

This script will activate the virtual environment, install dependencies, and start the Uvicorn server. The API will be available at http://127.0.0.1:8000.
Auto-start on Login (macOS)

An AppleScript application can be created to automatically open a Terminal window and run the run_app.sh script on user login. See the conversation history for the script and setup instructions.
API Endpoints

All jobs are triggered by sending a POST request to the appropriate endpoint.

    Daily Data Sync: Syncs recently updated Jira issues to the database.

    curl -X POST [http://127.0.0.1:8000/jobs/daily](http://127.0.0.1:8000/jobs/daily)

    Release Analysis: Triggers a full analysis of release-related data, including the initiative analysis.

    curl -X POST [http://127.0.0.1:8000/jobs/release](http://127.0.0.1:8000/jobs/release)

    Initiative Analysis (Manual): Manually re-runs the initiative-to-child mapping.

    curl -X POST [http://127.0.0.1:8000/jobs/initiative-analysis](http://127.0.0.1:8000/jobs/initiative-analysis)

    Icebox Automation: Runs the icebox management script.

    curl -X POST [http://127.0.0.1:8000/jobs/jiraicebox](http://127.0.0.1:8000/jobs/jiraicebox)

    Ticket Aging Report: Finds and logs tickets that have not been updated recently.

    curl -X POST [http://127.0.0.1:8000/jobs/ticket-aging](http://127.0.0.1:8000/jobs/ticket-aging)

    Daily Push Report: Generates an HTML report of recent merged pull requests.

    curl -X POST [http://127.0.0.1:8000/jobs/daily-pushes](http://127.0.0.1:8000/jobs/daily-pushes)

    Create RCA Sub-tasks: Finds critical bugs and creates RCA sub-tasks.

    curl -X POST [http://127.0.0.1:8000/jobs/create-rca-subtasks](http://127.0.0.1:8000/jobs/create-rca-subtasks)

    Data Quality Report: Generates a CSV report of tickets with missing data.

    curl -X POST [http://127.0.0.1:8000/jobs/data-quality-report](http://127.0.0.1:8000/jobs/data-quality-report)

    Customer Bug Analysis: Finds, updates, and reports on open customer bugs.

    curl -X POST [http://127.0.0.1:8000/jobs/customer-analysis](http://127.0.0.1:8000/jobs/customer-analysis)

Scheduled Tasks (Cron Jobs)

The project uses cron to automate the daily execution of certain jobs.
macOS Permissions

For cron to work correctly on modern macOS, you must grant it Full Disk Access in System Settings > Privacy & Security.
Crontab Setup

Use crontab -e to edit your cron jobs. The following entries schedule the daily tasks to run every weekday at 9:00 AM.

# Run the daily data sync and icebox jobs every weekday at 9:00 AM
0 9 * * 1-5 /path/to/jira_server/run_daily_job.sh
0 9 * * 1-5 /path/to/jira_server/run_icebox_job.sh

# Run the daily push report job every weekday at 9:15 AM
15 9 * * 1-5 /path/to/jira_server/run_pushes_job.sh

These scripts use curl to trigger the server's endpoints, and their output is logged to files in the logs/ directory.