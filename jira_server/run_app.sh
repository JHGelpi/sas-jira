#!/bin/bash

# This script starts the FastAPI application using Uvicorn.
# It's recommended to run this inside a virtual environment
# where all dependencies from requirements.txt are installed.

# Exit immediately if a command exits with a non-zero status.
set -e

# The directory where the main.py file is located
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
cd "$APP_DIR"

echo "Starting FastAPI server with Uvicorn..."
echo "API will be available at http://127.0.0.1:8000"
echo "Press CTRL+C to stop the server."

# Run the Uvicorn server
# --host 0.0.0.0 makes it accessible from outside the Docker container
# --port 8000 is the standard port
# --reload will automatically restart the server when code changes (for development)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload


# --- HOW TO TRIGGER JOBS ---
#
# Once the server is running, you can trigger jobs by sending POST requests
# to the API endpoints using a tool like 'curl'.
#
# Open a NEW terminal window and run the following commands:
#
# 1. To trigger the daily job:
#    curl -X POST http://127.0.0.1:8000/jobs/daily
#
# 2. To manually trigger a full release analysis:
#    curl -X POST http://127.0.0.1:8000/jobs/release
#
# You can monitor the progress by watching the logs in the terminal where
# the Uvicorn server is running.