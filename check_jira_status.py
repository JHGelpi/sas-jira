#!/usr/bin/env python3
"""Check COMPDIV-30 Jira status."""

import os
from pathlib import Path
from jira import JIRA

# Load environment
from dotenv import load_dotenv
dotenv_path = Path(__file__).parent / 'jira_server' / '.env'
load_dotenv(dotenv_path=dotenv_path)

def main():
    """Check COMPDIV-30 Jira status."""
    jira_url = os.getenv('JIRA_URL')
    jira_token = os.getenv('JIRA_TOKEN')

    jira = JIRA(server=jira_url, token_auth=jira_token)

    try:
        issue = jira.issue('COMPDIV-30', fields='key,status,summary')
    except Exception as e:
        print(f"Error fetching COMPDIV-30: {e}")
        print("\nCOMPDIV-30 may not exist or may have been moved/renamed")
        return

    print(f"Issue: {issue.key}")
    print(f"Summary: {issue.fields.summary}")
    print(f"Status: {issue.fields.status.name}")
    print(f"Status Category: {issue.fields.status.statusCategory.name}")
    print(f"Status Category Key: {issue.fields.status.statusCategory.key}")

    if issue.fields.status.statusCategory.name.lower() == "done":
        print("\n✓ Issue IS in 'Done' status category - should be closed")
    else:
        print("\n✗ Issue is NOT in 'Done' status category - should remain active")

if __name__ == '__main__':
    main()
