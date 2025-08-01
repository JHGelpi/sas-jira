#!/bin/bash

#cronjob entry
#5 2 * * * /Users/wegelpi/github_repos/sas-jira/jira-automation/jira_automation_run.sh >> /Users/wegelpi/github_repos/sas-jira/jira_server/jira_automation/logs/jira_automation.log 2>&1

# Navigate to the project directory
cd /Users/wegelpi/github_repos/sas-jira/jira_automation

# Activate the virtual env
# source /path/to/virtual/env

#Run the python script
/usr/local/bin/python3 main.py
