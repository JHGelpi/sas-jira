from jira import JIRA
import sys
import csv
from datetime import datetime
from utils import (parse_sprint_data, add_oper_epic, triage_parser, oper_parser, 
                   escaped_bug_flag, format_date, export_to_csv, 
                   parse_label_data, parse_fix_version_data, parse_component_data, build_jql_completed,
                   build_jql_active, append_csv, create_connection, setup_jira_client, fetch_issues, jira_obj_isrelated,
                   compdiv_initiatives, get_config_data)

def main():
    
    start_date = datetime.now()
    formatted_start_date = start_date.strftime('%d-%m-%y %H:%M:%S')
    postgres_log_start_date = formatted_start_date
    print("Starting at....", formatted_start_date)
    config_data = get_config_data()
    print("Configuration loaded successfully.")
    jira = setup_jira_client()
    if jira is None:
        print("Failed to initialize JIRA client. Ensure your configuration and credentials are correct.")
        sys.exit(1)  # Exit the program if JIRA client setup fails
    print("JIRA client initialized successfully.")
    
    if config_data['sprints'] == 'current':
        all_issues = fetch_issues(jira, build_jql_active())
    else:
        all_issues = fetch_issues(jira, build_jql_completed())
    print(f"Fetched {len(all_issues)} issues.")
    process_and_export_issues(all_issues)
    
    print ("Looking for new initiatives...")
    compdiv_initiatives()
    print ("Finished updating initiatives...")

    end_date = datetime.now()
    formatted_end_date = end_date.strftime('%d-%m-%y %H:%M:%S')
    postgres_log_end_date = formatted_end_date
    update_postgres_logs(postgres_log_start_date, postgres_log_end_date, config_data['sprints'])
    print("Completed at...", formatted_end_date)

def update_postgres_logs(postgres_log_start_date, postgres_log_end_date, jira_sprint):
    config_data = get_config_data()
    jira_sprint = config_data['sprints'][0]

    print("Updating PostgreSQL logs...")
    # Convert dates to the format 'YYYY-MM-DD HH:MM:SS'
    try:
        start_date_formatted = datetime.strptime(postgres_log_start_date, "%d-%m-%y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
        end_date_formatted = datetime.strptime(postgres_log_end_date, "%d-%m-%y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError as e:
        print(f"Date format error: {e}")
        return

    conn = None
    cursor = None

    conn = create_connection()
    if conn is None:
        print("Failed to establish database connection.")
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
            VALUES (%(exec_origin)s, %(start_date)s, %(end_date)s, %(sprint)s, %(run_type)s);
        """
        log_record = {
            "exec_origin": exec_origin,
            "start_date": start_date_formatted,
            "end_date": end_date_formatted,
            "sprint": jira_sprint,
            "run_type": run_type
        }

        # Execute the parameterized query
        print("Executing SQL Query:", sql_query)

        cursor.execute(sql_query, log_record)
        conn.commit()
        print("PostgreSQL logs updated successfully.")

        cursor.close()

    except Exception as e:
        print(f"Failed to process the file: {e}")
    finally:
        # Closing the connection
        if cursor:
            cursor.close()  # Close the cursor
        if conn:
            conn.close()  # Close the database connection

def process_and_export_issues(all_issues):
    print("Processing and exporting issues...")
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    config_data = get_config_data()
    output_path_trunk = config_data['output_base_path']
    csv_file = f'{output_path_trunk}jira-output-{timestamp}.csv'
    print(f"Exporting issues to CSV: {csv_file}")
    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
        writer.writerow(config_data['csv_headers'])
        for issue in all_issues:
            row = build_row(issue, config_data['jira_server'], config_data['output_base_path'])
            writer.writerow(row)
    print(f"CSV export complete: {csv_file}")
    export_to_csv(csv_file)
    append_csv(csv_file, 'hist', config_data['output_base_path'])

def build_row(issue, jira_server, folder_trunk):
    print(f"Building row for issue: {issue.key}")
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
    oper_epic = add_oper_epic(epic_link)
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
    created_date = format_date(issue.fields.created)
    updated_date = format_date(issue.fields.updated)
    if story_points == None:
        story_points = 0.0
    related_obj = jira_obj_isrelated(issue.key)
    if related_obj != "No Parent":
        parent_link = related_obj
    else:
        parent_link = None
    
    print (f"Related objects: {parent_link}")
    print(f"Row built for issue: {issue.key}")
    return [epic_link, parent_link,oper_epic, oper_flg, triage_flg, pipeline_stage, \
            bug_origin, escaped_bug, fix_version, components, issue.key, issue.fields.summary, \
            issue_url, type, parsed_sprint_data[0], assignee, status, sprint_start_date, \
            sprint_end_date, completed_date, parsed_sprint_data[3], labels, parsed_sprint_data[4], export_date, story_points, \
            created_date, updated_date]

if __name__ == '__main__':
    main()
