#!/bin/bash
# File: run_catchup_jobs.sh
# This script runs all scheduled jobs in the order defined by crontab_schedules.txt
# with a 10-second pause between each job execution.
# This is intended for manual catch-up runs when scheduled jobs were missed.

# Exit immediately if a command exits with a non-zero status.
set -e

# The absolute path to your project directory.
PROJECT_DIR="/Users/wegelpi/github_repos/sas-jira/jira_server"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/catchup_jobs.log"
TIMESTAMP=$(date +"%Y-%m-%d %T")

# Create the log directory if it doesn't exist to prevent errors.
mkdir -p "$LOG_DIR"

# --- Start Catch-Up Run ---
echo "=======================================" | tee -a "$LOG_FILE"
echo "[$TIMESTAMP] Starting catch-up job run..." | tee -a "$LOG_FILE"
echo "Running all jobs in crontab order with 10-second pauses" | tee -a "$LOG_FILE"
echo "=======================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Array of scripts in crontab order (8:15 AM - 8:24 AM)
SCRIPTS=(
    "run_ldap_refresh.sh"
    "run_customer_analysis.sh"
    "run_pushes_job.sh"
    "run_derive_data.sh"
    "run_data_quality.sh"
    "run_rca_st_job.sh"
    "run_icebox_job.sh"
    "run_daily_job.sh"
    "run_bug_trending_analysis.sh"
    "run_compdiv_burndown.sh"
    "run_burndown_dashboard.sh"
)

# Total number of scripts
TOTAL=${#SCRIPTS[@]}
CURRENT=0

# Run each script in order
for SCRIPT in "${SCRIPTS[@]}"; do
    CURRENT=$((CURRENT + 1))
    SCRIPT_PATH="${PROJECT_DIR}/${SCRIPT}"
    SCRIPT_TIMESTAMP=$(date +"%Y-%m-%d %T")

    echo "[$SCRIPT_TIMESTAMP] [${CURRENT}/${TOTAL}] Running ${SCRIPT}..." | tee -a "$LOG_FILE"

    # Check if script exists and is executable
    if [ -f "$SCRIPT_PATH" ] && [ -x "$SCRIPT_PATH" ]; then
        # Execute the script
        "$SCRIPT_PATH"
        EXIT_CODE=$?

        if [ $EXIT_CODE -eq 0 ]; then
            echo "[$SCRIPT_TIMESTAMP] [${CURRENT}/${TOTAL}] ✓ ${SCRIPT} completed successfully" | tee -a "$LOG_FILE"
        else
            echo "[$SCRIPT_TIMESTAMP] [${CURRENT}/${TOTAL}] ✗ ${SCRIPT} failed with exit code ${EXIT_CODE}" | tee -a "$LOG_FILE"
        fi
    else
        echo "[$SCRIPT_TIMESTAMP] [${CURRENT}/${TOTAL}] ⚠ ${SCRIPT} not found or not executable at ${SCRIPT_PATH}" | tee -a "$LOG_FILE"
    fi

    # Pause for 10 seconds between scripts (except after the last one)
    if [ $CURRENT -lt $TOTAL ]; then
        echo "   Waiting 10 seconds before next job..." | tee -a "$LOG_FILE"
        echo "" | tee -a "$LOG_FILE"
        sleep 10
    fi
done

# --- Completion ---
FINISH_TIMESTAMP=$(date +"%Y-%m-%d %T")
echo "" | tee -a "$LOG_FILE"
echo "=======================================" | tee -a "$LOG_FILE"
echo "[$FINISH_TIMESTAMP] Catch-up job run completed!" | tee -a "$LOG_FILE"
echo "All ${TOTAL} jobs have been executed." | tee -a "$LOG_FILE"
echo "=======================================" | tee -a "$LOG_FILE"
