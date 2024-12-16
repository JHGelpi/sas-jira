from jira import JIRA
import sys
import csv
from datetime import datetime
from utils import (parse_sprint_data, add_oper_epic, triage_parser, oper_parser, 
                   escaped_bug_flag, format_date, export_to_csv, load_config, 
                   parse_label_data, parse_fix_version_data, parse_component_data, build_jql_completed,
                   build_jql_active, append_csv, create_connection, setup_jira_client)

def main():
    '''
    Main function to get the data for the Program Manager's data requirements
    
    Fields needed: 
    area - derived value representing a Department (e.g. 'CAS Compute')
    issue_type - Type of jira issue (Story, Bug, etc.)
    issue_status - Current status of the issue (In Progress)
    initiative_summary - Summary of the initiative (e.g. 'Update PRINT statement documentation for PROC CAS/CASL')
    initiative_url - URL for initiative (e.g. 'https://rndjira.sas.com/browse/COMPDIV-14')
    issue_summary - Summary of issue (e.g. 'Update PRINT statement documentation for PROC CAS/CASL')
    fix_version - Fix version (e.g. 2024.12)
    sprint_month - End date of sprint (e.g. 2024.11 sprint would have a value of 2024-11-15)
    story_points_est - Story points from issue
    category - Categorization of the story (e.g. PM Requirements) - This will have to be a config file/lookup
    effective_date - Date the download of the data occurred
    '''
    
    start_date = datetime.now()
    formatted_start_date = start_date.strftime('%d-%m-%y %H:%M:%S')
    postgres_log_start_date = formatted_start_date
    print("Starting at....", formatted_start_date)
    config = load_config('/Users/wegelpi/jira/helper_files/config.json')
    jira = setup_jira_client(config)
    if jira is None:
        print("Failed to initialize JIRA client. Exiting.")
        sys.exit(1)  # Exit the program if JIRA client setup fails


if __name__ == '__main__':
    main()