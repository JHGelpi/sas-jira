#!/bin/bash
# File: run_daily_job.sh (Updated)
# This script now uses curl to trigger the FastAPI server endpoint.

# The absolute path to your project directory.
PROJECT_DIR="/Users/wegelpi/github_repos/sas-jira/jira_server"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/cron_daily.log"
TIMESTAMP=$(date +"%Y-%m-%d %T")

# Create the log directory if it doesn't exist to prevent errors.
mkdir -p "$LOG_DIR"

# --- Execution ---
echo "---" >> "$LOG_FILE"
echo "[$TIMESTAMP] Cron job started: Triggering /jobs/daily endpoint..." >> "$LOG_FILE"

# Execute the curl command to trigger the API.
# The -s flag makes curl silent (no progress meter).
# The output and any errors are redirected to the log file.
/usr/bin/curl -s -X POST http://127.0.0.1:8000/jobs/daily >> "$LOG_FILE" 2>&1

echo "" >> "$LOG_FILE"
echo "[$TIMESTAMP] Cron job finished." >> "$LOG_FILE"