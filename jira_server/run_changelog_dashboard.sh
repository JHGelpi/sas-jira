#!/bin/bash
# File: run_changelog_dashboard.sh

# This script is designed to be run by a cron job to trigger the changelog
# activity dashboard generation. It collects changelog data and generates
# the interactive HTML dashboard.

# The absolute path to your project directory.
PROJECT_DIR="/Users/wegelpi/github_repos/sas-jira/jira_server"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/cron_changelog_dashboard.log"
TIMESTAMP=$(date +"%Y-%m-%d %T")

# Create the log directory if it doesn't exist to prevent errors.
mkdir -p "$LOG_DIR"

# --- Execution ---
echo "---" >> "$LOG_FILE"
echo "[$TIMESTAMP] Cron job started: Triggering /jobs/generate-changelog-dashboard endpoint..." >> "$LOG_FILE"

# Execute the curl command to trigger the API.
# Note: The endpoint automatically runs changelog collection first
/usr/bin/curl -s -X POST http://127.0.0.1:8000/jobs/generate-changelog-dashboard >> "$LOG_FILE" 2>&1

echo "" >> "$LOG_FILE"
echo "[$TIMESTAMP] Cron job finished." >> "$LOG_FILE"
