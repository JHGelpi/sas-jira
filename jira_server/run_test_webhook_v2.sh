#!/bin/bash

# Test script for Teams Webhook V2 integration
# This script sends a test notification to verify the new Power Automate webhook works

echo "=== Teams Webhook V2 Test ==="
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "Error: Virtual environment not found. Please run ./run_app.sh first to set up."
    exit 1
fi

# Set Python path to include the jira_automation module
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# Run the test script
echo "Running webhook test..."
echo ""
python test_teams_webhook_v2.py

# Deactivate virtual environment
deactivate

echo ""
echo "=== Test Complete ==="
