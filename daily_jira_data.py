'''
I need to import jira data using my existing API configuration.  
I plan on running the import every day.  The import will import all jira items for a 
specific set of projects that will be defined by environment variables in my .env file.  
I will want to import any jira items that have changed status in the past 24 hours and 
write them to my postgres db.  This will run inside a docker container.
'''
import os
import csv
import json
import psycopg2
from datetime import datetime, timedelta
from fastapi import FastAPI
from jira import JIRA
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

def setup_jira_client():
    # Database connection
    #conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    #cursor = conn.cursor()
    #options = {'server': conn}
    jira_api_token = os.getenv('JIRA_TOKEN')
    jira_url = os.getenv('JIRA_URL')

    jira = JIRA(
        server=jira_url,
        token_auth=jira_api_token
    )

    #jira = JIRA(options=options, token_auth=jira_api_token)
    ## Set the Authorization header on the session object directly
    jira._session.headers.update({'Authorization': f'Bearer {jira_api_token}'})

    return jira

def create_connection():
    """ Create and return a PostgreSQL connection using the given connection string. """
    db_password = os.getenv('DB_PASSWORD')
    db_user = os.getenv('DB_USER')
    db_name = os.getenv('DB_NAME')
    db_host = os.getenv('DB_HOST')
    db_timeout = os.getenv('DB_CONN_TIMEOUT')
    
    conn_string = f"dbname='{db_name}' user='{db_user}' password='{db_password}' host='{db_host}' connect_timeout={db_timeout} sslmode='prefer'"

    conn = psycopg2.connect(conn_string)
    return conn

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
    if story_points == None:
        story_points = 0.0
    related_obj = jira_obj_isrelated(issue.key)
    if related_obj != "No Parent":
        parent_link = related_obj
    else:
        parent_link = None
    
    print (f"Related objects: {parent_link}")
    print(f"Row built for issue: {issue.key}")
    return [epic_link, parent_link,oper_epic, oper_flg, triage_flg, pipeline_stage, bug_origin, escaped_bug, fix_version, components, issue.key, issue.fields.summary, issue_url, type, parsed_sprint_data[0], assignee, status, sprint_start_date, sprint_end_date, completed_date, parsed_sprint_data[3], labels, parsed_sprint_data[4], export_date, story_points]

def process_and_export_issues(all_issues):
    print("Processing and exporting issues...")
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    #config_data = get_config_data()
    output_dir = os.getenv('OUTPUT_DIR')
    csv_file = f'{output_dir}jira-output-{timestamp}.csv'
    print(f"Exporting issues to CSV: {csv_file}")
    
    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
        writer.writerow(os.getenv("CSV_HEADERS").split(','))
        for issue in all_issues:
            row = build_row(issue, os.getenv("JIRA_URL"), output_dir)
            writer.writerow(row)
    print(f"CSV export complete: {csv_file}")
    #export_to_csv(csv_file)
    append_csv(csv_file, 'daily', output_dir)

def update_postgres_logs(postgres_log_start_date, postgres_log_end_date, jira_sprint):
    #config_data = get_config_data()
    #jira_sprint = config_data['sprints'][0]

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

def append_csv(csv_file, tbl_flag, folder_trunk):
    conn = None
    cursor = None

    conn = create_connection()
    if conn is None:
        return
    
    # Connect to JIRA
    config_file = f'{folder_trunk}helper_files/config.json'

    try:
        with open(config_file, 'r') as file:
            config = json.load(file)
        
        #postgres_cols = tuple(config_file['postgres_cols'])
        postgres_cols = tuple(config['postgres_cols'])

        with open(csv_file, 'r', newline='', encoding='utf-8') as f:
            next(f)  # Skip header
            cursor = conn.cursor()
            if tbl_flag == 'hist':
                sql_query = f"""
                    COPY tbl_jira_sprint_data ({','.join(postgres_cols)})
                    FROM STDIN WITH CSV HEADER DELIMITER ',' QUOTE '\"' NULL 'NULL'
                    """
                print ("SQL Statement from append_csv: ", sql_query)
                cursor.copy_expert(sql_query, f)

                conn.commit()
                cursor.close()
                print(f"Data appended successfully from {csv_file}")
            elif tbl_flag == 'curr':
                sql_query = f"""
                    COPY tbl_jira_active_tickets ({','.join(postgres_cols)})
                    FROM STDIN WITH CSV HEADER DELIMITER ',' QUOTE '\"' NULL 'NULL'
                    """
                cursor.copy_expert(sql_query, f)

                conn.commit()
                cursor.close()
                print(f"Data appended successfully from {csv_file}")
    except Exception as e:
        print(f"Failed to process the file: {e}")
    finally:
        # Closing the connection
        if cursor:
            cursor.close()  # Close the cursor
        if conn:
            conn.close()  # Close the database connection

def add_oper_epic(epic_name):
    """
    Determine the operational epic based on the epic link.
    
    :param epic_name: The name of the epic to look for.
    :param folder_trunk: The folder path (unused but kept for compatibility).
    :return: The sprint team associated with the epic or an empty string if no match is found.
    """
    # Return early if epic_name is None or empty
    if not epic_name:
        return ''
    
    # Database connection
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cursor = conn.cursor()

    try:
        # Query to find the sprint team associated with the epic
        query = """
            SELECT sprint_team
            FROM tbl_jira_oper_epics
            WHERE epic = %s
        """
        cursor.execute(query, (epic_name,))
        result = cursor.fetchone()

        if result:
            return result[0]  # Return the sprint team
        else:
            return ''  # Return empty string if no matching epic is found
    finally:
        cursor.close()
        conn.close()

def triage_parser(labels):
    """Parse and analyze the triage labels."""
    collector_label = 'collector-59dc380c'
    if collector_label in labels:
        return True
    else:
        return False

def oper_parser(labels):
    """Parse and analyze the operational flags from labels."""
    required_updates_label = 'required_updates'
    if required_updates_label in labels:
        return True
    else:
        return False

def escaped_bug_flag(origin, pipeline_stage):
    """Determine if a bug escaped based on its origin and pipeline stage."""
    if not origin or not pipeline_stage:
        return False
    
    if 'CRP' in origin and pipeline_stage == 'Shipped':
        return True
    else: 
        return False
    
def format_date(date_str):
    """Format date string to a specific format or handle null values."""
    # Check if the date string is a placeholder for missing values
    if date_str == '<null>':
        date_string = '1900-12-12 12:00:00+00:00'
        date_time_obj = datetime.strptime(date_string, '%Y-%m-%d %H:%M:%S%z')  
        return date_time_obj
    # Parse the datetime from the given string format
    try:
        date_object = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S.%f%z')
        # Convert the datetime object to just the date in 'yyyy-mm-dd' format
        formatted_date = date_object.strftime('%Y-%m-%d')
        return formatted_date
    except ValueError as e:
        print(f"Error parsing date: {date_str} - {e}")
        date_string = '1900-12-12 12:00:00+00:00'
        date_time_obj = datetime.strptime(date_string, '%Y-%m-%d %H:%M:%S%z')  
        return date_time_obj

'''# Load sprint manager data from JSON into a list of project names
def load_projects(filename):
    projects = []
    with open(filename, mode='r', encoding='utf-8') as file:
        data = json.load(file)
        # Access the list of projects under the key 'jira-project-owners'
        for item in data.get("jira-project-owners", []):
            project_name = item.get("Project", "").strip()
            if project_name:  # Check if project_name is not empty
                projects.append(project_name)
    return projects'''

def parse_component_data(components):
    """Parse component data from JIRA issue fields."""
    if not components:
        return ''

    # Initialize a list to store component names
    component_names = []

    # Iterate over each component in the list
    for component in components:
        # Check if the component has a name attribute
        if hasattr(component, 'name') and component.name:
            component_names.append(component.name)
        else:
            component_names.append('No Component Name')

    # Join all component names into a single string separated by commas
    return '|'.join(component_names)

def parse_fix_version_data(components):
    """Parse fix version data from JIRA issue fields."""
    if not components:
        return ''

    # Initialize a list to store component names
    component_names = []

    # Iterate over each component in the list
    for component in components:
        # Check if the component has a name attribute
        if hasattr(component, 'name') and component.name:
            component_names.append(component.name)
        else:
            component_names.append('')

    # Join all component names into a single string separated by commas
    return '|'.join(component_names)

def parse_label_data(labels):
    """Parse label data from JIRA issue fields."""
    if not labels:
        return ''
    
    # Initialize a list to store label names
    label_names = []

    # Iterate over each label in the list
    for label in labels:
        # Ensure that label is a string, if the label structure is simple and contains direct string items
        label_names.append(str(label))  # Converts label to string if it's not already
    
    return '|'.join(label_names)

def jira_obj_isrelated(issue_key):
    """
    Retrieve and process issue relationships (links, parent, sub-tasks) for a given JIRA issue.

    Parameters:
    - issue_key (str): The JIRA issue key to fetch relationships for.

    Returns:
    - None
    """
    
    try:

        # Initialize JIRA client
        jira = setup_jira_client()
        if jira is None:
            raise Exception("Failed to initialize JIRA client. Check configuration and credentials.")
        print ("JIRA client initialized successfully.")

        # Fetch issue details
        print (f"Fetching details for issue: {issue_key}")
        issue_data = jira.issue(issue_key, fields="issuelinks,parent,subtasks")
        fields = issue_data.fields

        # Process issue links
        issue_links = getattr(fields, "issuelinks", [])
        print ("Processing issue links...")
        for link in issue_links:
            link_type = link.type.name
            inward = getattr(link, "inwardIssue", None)
            outward = getattr(link, "outwardIssue", None)
            
            if inward:
                print (f"{link_type} (Inward): {inward.key} - {inward.fields.summary}")
            if outward:
                print (f"{link_type} (Outward): {outward.key} - {outward.fields.summary}")

        # Parent issue
        parent = getattr(fields, "parent", None)
        if parent:
            print (f"Parent Issue: {parent.key} - {parent.fields.summary}")
            parent_key = parent.key
        else:
            print ("No parent issue found.")
            parent_key = "No Parent"

        # Sub-tasks
        subtasks = getattr(fields, "subtasks", [])
        if subtasks:
            print ("Processing sub-tasks...")
            for subtask in subtasks:
                print (f"Sub-task: {subtask.key} - {subtask.fields.summary}")
        else:
            print ("No sub-tasks found.")

        return parent_key
    except Exception as e:
        print (f"An error occurred: {e}")
        return None

def parse_sprint_data(sprint_string, folder_trunk):
    """Parse sprint data from the custom field format into structured data."""
    # Load the managers dictionary
    jira_helper_folder = f'{folder_trunk}helper_files/'
    jira_project_owner_file = str(jira_helper_folder) + 'config.json'

    sprint_managers = load_sprint_managers()

    # Handle None input early
    if sprint_string is None:
        return ['', '', '', '', '', '']

    # Ensure the sprint_string is a string and not empty
    if isinstance(sprint_string, list) and sprint_string:
        sprint_string = sprint_string[0]
    elif not isinstance(sprint_string, str) or not sprint_string:
        return ['', '', '', '', '', '']

    # Trim whitespace which might affect substring search
    sprint_string = sprint_string.strip()

    # Check for the presence of the desired pattern
    if 'state=' in sprint_string and 'startDate=' in sprint_string and 'endDate=' in sprint_string:
        # Extract the information
        state_index = sprint_string.find('state=') + len('state=')
        state = sprint_string[state_index:sprint_string.find(',', state_index)]

        sprint_name_index = sprint_string.find('name=') + len('name=')
        sprint_name = sprint_string[sprint_name_index:sprint_string.find(',', sprint_name_index)]
        
        sprint_owner = add_sprint_owner(sprint_managers, sprint_name)

        start_index = sprint_string.find('startDate=') + len('startDate=')
        start_date = sprint_string[start_index:sprint_string.find(',', start_index)]

        end_index = sprint_string.find('endDate=') + len('endDate=')
        end_date = sprint_string[end_index:sprint_string.find(',', end_index)]

        complete_date_index = sprint_string.find('completeDate=') + len('completeDate=')
        complete_date = sprint_string[complete_date_index:sprint_string.find(',', complete_date_index)]

        return [state, start_date, end_date, sprint_name, sprint_owner, complete_date]
    else:
        return ['', '', '', '', '', '']  # Handle cases where format does not match

def load_sprint_managers():
    """
    Load sprint manager data from the PostgreSQL table into a dictionary.
    
    :return: A dictionary with project names as keys and owners as values.
    """
    managers = {}
    
    # Database connection
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cursor = conn.cursor()

    try:
        # Query to get project-owner pairs from the table
        query = """
            SELECT project, owner
            FROM tbl_jira_project_owners
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        # Populate the managers dictionary with project-owner pairs
        for row in rows:
            project, owner = row
            if project and owner:
                managers[project] = owner
    finally:
        cursor.close()
        conn.close()
    
    return managers

def add_sprint_owner(sprint_managers, sprint_name):
    # sprint_owners = sprint_managers
    
    for team in sprint_managers:
        if sprint_name.startswith(team):
            #manager = sprint_managers[1]
            return sprint_managers[team]
    
    return 'No Manager'

def fetch_issues(jira, jql_query):
    start_at = 0
    max_results = 750
    all_issues = []
    retries = 0
    max_retries = 5
    print("Fetching issues from JIRA...")
    while True:
        try:
            print(f"Querying JIRA with startAt={start_at} and maxResults={max_results}...")
            issues = jira.search_issues(jql_query, startAt=start_at, maxResults=max_results)
            all_issues.extend(issues)
            print(f"Retrieved {len(issues)} issues.")
            if len(issues) < max_results:
                break
            start_at += len(issues)
        except Exception as e:
            retries += 1
            print(f"Error during JIRA fetch: {e}")
            if retries > max_retries:
                print(f"Failed after {max_retries} retries: {e}")
                break
            print(f"Retrying ({retries}/{max_retries}) due to error: {e}")
    print(f"Total issues fetched: {len(all_issues)}")
    return all_issues

def update_postgres_logs(postgres_log_start_date, postgres_log_end_date):
    #config_data = get_config_data()
    #jira_sprint = config_data['sprints'][0]
    jira_sprint = 'daily'
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
        run_type = 'DAILY'

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

def build_jql():
    # This function will look at the run logs and build the JQL statement based on the last log entry
    conn = create_connection()
    cursor = conn.cursor()

    sql_query = """
        SELECT MAX(endDTTM)
        FROM tbl_run_log
        WHERE "runType" = 'DAILY';
    """
    cursor.execute(sql_query)

    jql = f"project in ({os.getenv('JIRA_PROJECTS')}) AND updated >= '{cursor.fetchone()[0]}'"
    return jql