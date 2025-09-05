#!/bin/bash
# File: run_rca_st_job.sh

# This script is designed to be run by a cron job to trigger the daily RCA subtask update.

# The absolute path to your project directory.
PROJECT_DIR="/Users/wegelpi/github_repos/sas-jira/jira_server"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/cron_pushes.log"
TIMESTAMP=$(date +"%Y-%m-%d %T")

# Create the log directory if it doesn't exist to prevent errors.
mkdir -p "$LOG_DIR"

# --- Execution ---
echo "---" >> "$LOG_FILE"
#echo "[$TIMESTAMP] Cron job started: Triggering /jobs/collect-bug-snapshots endpoint..." >> "$LOG_FILE"

# Execute the curl command to trigger the API.
#/usr/bin/curl -s -X POST http://127.0.0.1:8000/jobs/collect-bug-snapshots >> "$LOG_FILE" 2>&1

echo "[$TIMESTAMP] Cron job started: Triggering /jobs/generate-bug-charts endpoint..." >> "$LOG_FILE"

# Execute the curl command to trigger the API.
/usr/bin/curl -s -X POST http://127.0.0.1:8000/jobs/generate-bug-charts >> "$LOG_FILE" 2>&1

echo "" >> "$LOG_FILE"
echo "[$TIMESTAMP] Cron job finished." >> "$LOG_FILE"
