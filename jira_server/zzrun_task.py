# File: run_task.py
# Purpose: A dedicated script for cron to execute specific tasks directly.
# Save this file in your main 'jira_server' directory.

import sys
import os
from dotenv import load_dotenv

def main():
    """
    Runs a specific task based on a command-line argument.
    """
    # Add the project root to the Python path to allow for absolute imports
    # This makes the script runnable from anywhere.
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root)

    # Load the .env file to get all necessary environment variables
    dotenv_path = os.path.join(project_root, '.env')
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
    else:
        print(f"Error: .env file not found at {dotenv_path}")
        sys.exit(1)

    # Now that the environment is set up, we can import our tasks
    from tasks import run_jira_export_task, run_jira_icebox_task

    if len(sys.argv) < 2:
        print("Usage: python3 run_task.py <task_name>")
        print("Available tasks: daily, icebox")
        sys.exit(1)

    task_name = sys.argv[1]

    print(f"Executing task: {task_name}")

    if task_name == "daily":
        run_jira_export_task('daily')
    elif task_name == "icebox":
        run_jira_icebox_task()
    else:
        print(f"Error: Unknown task '{task_name}'")
        sys.exit(1)
    
    print(f"Task '{task_name}' finished successfully.")

if __name__ == "__main__":
    main()