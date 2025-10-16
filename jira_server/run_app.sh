#!/bin/bash

# This script prepares the environment and starts the FastAPI application.
# It ensures a virtual environment is active and all dependencies are installed.

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Cleanup function ---
# This function will be called when the script exits to ensure cleanup.
cleanup() {
    echo -e "\n--- Script interrupted or finished. Deactivating virtual environment. ---"
    # The 'deactivate' command is only available if the venv was successfully sourced.
    # We check if the command exists before trying to run it.
    if command -v deactivate &> /dev/null; then
        deactivate
    fi
}

# Trap the EXIT signal to run the cleanup function.
# This ensures that 'deactivate' is called even if the script is stopped with Ctrl+C.
trap cleanup EXIT

# The directory where this script is located
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
cd "$APP_DIR"

VENV_DIR="venv"

# --- Environment Setup ---

# 1. Check if the virtual environment directory exists.
if [ ! -d "$VENV_DIR" ]; then
    echo "Virtual environment not found. Creating one at '$VENV_DIR/'..."
    # Use python3 to create the virtual environment
    python3 -m venv "$VENV_DIR"
fi

# 2. Activate the virtual environment.
# This command makes 'uvicorn' and other packages available.
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# 3. Upgrade pip to the latest version.
echo "Upgrading pip to the latest version..."
pip install --upgrade pip

# 4. Install/update dependencies from requirements.txt.
echo "Installing/updating dependencies from requirements.txt..."
pip install -r requirements.txt

echo -e "\n--- Environment setup complete ---"

# --- Start Server ---

echo "Starting FastAPI server with Uvicorn..."
echo "API will be available at http://127.0.0.1:8000"
echo "View interactive API docs at http://127.0.0.1:8000/docs"
echo "Press CTRL+C to stop the server."

# Run the Uvicorn server. Now that the venv is active, the 'uvicorn' command will be found.
# --host 0.0.0.0 makes it accessible from outside a Docker container if you use one.
uvicorn main:app --host 0.0.0.0 --port 8000 --reload --log-config log_config.yaml

# The 'trap' command registered at the top will handle calling the 'cleanup' function upon exit.
