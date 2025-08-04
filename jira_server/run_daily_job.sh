#!/bin/bash
# File: run_daily_job.sh

# This script is designed to be run by a cron job to trigger the daily Jira sync.

# IMPORTANT: Update this path if your project is located elsewhere.
PROJECT_DIR="/Users/wegelpi/github_repos/sas-jira/jira_server"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/cron_daily.log"
TIMESTAMP=$(date +"%Y-%m-%d %T")

# --- Create the log directory if it doesn't exist ---
mkdir -p "$LOG_DIR"

# --- Execution ---
echo "---" >> "$LOG_FILE"
echo "[$TIMESTAMP] Cron job started: Triggering /jobs/daily" >> "$LOG_FILE"

/usr/bin/curl -s -X POST http://127.0.0.1:8000/jobs/daily >> "$LOG_FILE" 2>&1

echo "" >> "$LOG_FILE"
echo "[$TIMESTAMP] Cron job finished." >> "$LOG_FILE"