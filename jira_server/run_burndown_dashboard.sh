#!/bin/bash
# File: run_burndown_dashboard.sh

# This script triggers the burndown dashboard generation job.
# It can be run manually or via cron to regenerate the dashboard.

# The absolute path to your project directory.
PROJECT_DIR="/Users/wegelpi/github_repos/sas-jira/jira_server"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/cron_burndown_dashboard.log"
TIMESTAMP=$(date +"%Y-%m-%d %T")

# Create the log directory if it doesn't exist to prevent errors.
mkdir -p "$LOG_DIR"

# --- Execution ---
echo "---" >> "$LOG_FILE"
echo "[$TIMESTAMP] Job started: Triggering /jobs/generate-burndown-dashboard endpoint..." >> "$LOG_FILE"

# Execute the curl command to trigger the API.
/usr/bin/curl -s -X POST http://127.0.0.1:8000/jobs/generate-burndown-dashboard >> "$LOG_FILE" 2>&1

echo "" >> "$LOG_FILE"
echo "[$TIMESTAMP] Job finished." >> "$LOG_FILE"
