#!/bin/bash
# File: run_iris_burndown.sh

# This script is designed to be run by a cron job to trigger the IRIS burndown analysis.

# The absolute path to your project directory.
PROJECT_DIR="/Users/wegelpi/github_repos/sas-jira/jira_server"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/cron_iris_burndown.log"
TIMESTAMP=$(date +"%Y-%m-%d %T")

# Create the log directory if it doesn't exist to prevent errors.
mkdir -p "$LOG_DIR"

# --- Execution ---
echo "---" >> "$LOG_FILE"
echo "[$TIMESTAMP] Cron job started: Triggering /jobs/iris-burndown endpoint..." >> "$LOG_FILE"

# Execute the curl command to trigger the API.
/usr/bin/curl -s -X POST http://127.0.0.1:8000/jobs/iris-burndown >> "$LOG_FILE" 2>&1

echo "" >> "$LOG_FILE"
echo "[$TIMESTAMP] Cron job finished." >> "$LOG_FILE"
