from jira import JIRA
import sys
import csv
# import json
from datetime import datetime
from utils import (parse_sprint_data, add_oper_epic, triage_parser, oper_parser, 
                   escaped_bug_flag, format_date, export_to_csv, load_config, 
                   parse_label_data, parse_fix_version_data, parse_component_data, build_jql_completed,
                   build_jql_active, append_csv, create_connection)

def main():
    
    start_date = datetime.now()
    formatted_start_date = start_date.strftime('%d-%m-%y %H:%M:%S')
    postgres_log_start_date = formatted_start_date
    print("Starting at....", formatted_start_date)
    config = load_config('/Users/wegelpi/jira/helper_files/config.json')
    jira = setup_jira_client(config)
    if jira is None:
        print("Failed to initialize JIRA client. Exiting.")
        sys.exit(1)  # Exit the program if JIRA client setup fails
    
    sprint = config['sprints'][0]
    
    if config['sprints'] == 'current':
        all_issues = fetch_issues(jira, build_jql_active(sprint, config['output_base_path']))
    else:
        all_issues = fetch_issues(jira, build_jql_completed(sprint, config['output_base_path']))
        process_and_export_issues(all_issues, config)
    
    end_date = datetime.now()
    formatted_end_date = end_date.strftime('%d-%m-%y %H:%M:%S')
    postgres_log_end_date = formatted_end_date
    update_postgres_logs(postgres_log_start_date, postgres_log_end_date, sprint)
    print("Completed at...", formatted_end_date)

def setup_jira_client(config):
    try:
        options = {'server': config['jira_server']}
        file_path = str(config['secret_folder']) + 'jira-token.txt'
        with open(file_path, 'r') as file:
            jira_api_token = file.read().strip()

        jira = JIRA(options=options, token_auth=jira_api_token)

        ## Set the Authorization header on the session object directly
        jira._session.headers.update({'Authorization': f'Bearer {jira_api_token}'})
        return jira
    except Exception as e:
        print(f"Failed to initialize JIRA client: {e}")
        return None

def update_postgres_logs(postgres_log_start_date, postgres_log_end_date, jira_sprint):
    config = load_config('/Users/wegelpi/jira/helper_files/config.json')
    jira_sprint = config['sprints'][0]

    # Convert dates to the format 'YYYY-MM-DD HH:MM:SS'
    try:
        start_date_formatted = datetime.strptime(postgres_log_start_date, "%d-%m-%y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
        end_date_formatted = datetime.strptime(postgres_log_end_date, "%d-%m-%y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError as e:
        print(f"Date format error: {e}")
        return

    if jira_sprint == 'current':
        log_record = "VALUES('python', '{}', '{}', '{}', '{}')".format(start_date_formatted, end_date_formatted, jira_sprint, 'CURR')
    else:
        log_record = "VALUES('python', '{}', '{}', '{}', '{}')".format(start_date_formatted, end_date_formatted, jira_sprint, 'HIST')

    conn = None
    cursor = None

    conn = create_connection()
    if conn is None:
        return

    try:
        cursor = conn.cursor()
        if cursor is None:
            print("Failed to create a cursor.")
            return

        # Parameterized query to avoid syntax issues
        exec_origin = 'python'
        run_type = 'CURR' if jira_sprint == 'current' else 'HIST'

        sql_query = """
            INSERT INTO tbl_run_log ("execOrigin", "startDTTM", "endDTTM", "sprint", "runType") 
            VALUES (%s, %s, %s, %s, %s);
        """
        log_record = (exec_origin, start_date_formatted, end_date_formatted, jira_sprint, run_type)

        # Execute the parameterized query
        print("Executing SQL Query:", sql_query)

        cursor.execute(sql_query, log_record)
        conn.commit()

        cursor.close()

    except Exception as e:
        print(f"Failed to process the file: {e}")
    finally:
        # Closing the connection
        if cursor:
            cursor.close()  # Close the cursor
        if conn:
            conn.close()  # Close the database connection

def fetch_issues(jira, jql_query):
    start_at = 0
    max_results = 750
    all_issues = []
    while True:
        issues = jira.search_issues(jql_query, startAt=start_at, maxResults=max_results)
        all_issues.extend(issues)
        if len(issues) < max_results:
            break
        start_at += len(issues)
    return all_issues

def process_and_export_issues(all_issues, config):
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    output_path_trunk = config['output_base_path']
    csv_file = f'{output_path_trunk}jira-output-{timestamp}.csv'
    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
        writer.writerow(config['csv_headers'])
        for issue in all_issues:
            row = build_row(issue, config['jira_server'], config['output_base_path'])
            writer.writerow(row)
    export_to_csv(csv_file)
    append_csv(csv_file, 'hist', config['output_base_path'])

def build_row(issue, jira_server, folder_trunk):
    sprint_data_list = []
    start_date = datetime.now()

    # Extract and format necessary fields from issue
    assignee = issue.fields.assignee.displayName if issue.fields.assignee else 'Unassigned'
    status = issue.fields.status.name if issue.fields.status else 'No Status'
    type = issue.fields.issuetype if issue.fields.issuetype else 'No Type'
    sprint_data_string = getattr(issue.fields, 'customfield_10102', 'No Data')
    sprint_data_list.append((issue.key, sprint_data_string))
    parsed_sprint_data = parse_sprint_data(sprint_data_string, folder_trunk)
    sprint_start_date = format_date(parsed_sprint_data[1])
    sprint_end_date = format_date(parsed_sprint_data[2])
    completed_date = format_date(parsed_sprint_data[5])
    issue_url = f'{jira_server}browse/' + str(issue.key)
    epic_link = getattr(issue.fields, 'customfield_10301', '')
    parent_link = getattr(issue.fields, 'customfield_16301', 'No Parent')
    oper_epic = add_oper_epic(epic_link, folder_trunk)
    labels = parse_label_data(getattr(issue.fields, 'labels', ''))
    pipeline_stage = str(getattr(issue.fields, 'customfield_15600', ''))
    bug_origin = str(getattr(issue.fields, 'customfield_14504', ''))
    escaped_bug = 'Y' if escaped_bug_flag(bug_origin, pipeline_stage) else 'N'
    triage_flg = 'Y' if triage_parser(labels) else 'N'
    oper_flg = 'Y' if oper_parser(labels) else 'N'
    fix_version = parse_fix_version_data(getattr(issue.fields, 'fixVersions', ''))
    export_date = start_date.strftime('%Y-%m-%d %H:%M:%S')
    components = parse_component_data(getattr(issue.fields, 'components', ''))
    story_points = getattr(issue.fields, 'customfield_10002', 0)

    return [epic_link, parent_link,oper_epic, oper_flg, triage_flg, pipeline_stage, bug_origin, escaped_bug, fix_version, components, issue.key, issue.fields.summary, issue_url, type, parsed_sprint_data[0], assignee, status, sprint_start_date, sprint_end_date, completed_date, parsed_sprint_data[3], labels, parsed_sprint_data[4], export_date, story_points]

if __name__ == '__main__':
    main()
