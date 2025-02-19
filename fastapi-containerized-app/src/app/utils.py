from jira import JIRA
from datetime import datetime
import json
import psycopg2
from psycopg2.extras import execute_values

'''def get_config_data():
    """
    Load configuration data from the config file.

    :return: Dictionary containing configuration data
    """
    CONFIG_FILE_PATH = '/Users/wegelpi/jira/helper_files/'
    CONFIG_FILE = 'config.json'

    print("Loading configuration data from the config file.")
    try:
        with open(CONFIG_FILE_PATH + CONFIG_FILE, 'r') as file:
            config = json.load(file)

            # Extract and structure the configuration
            configuration = {
                'jira_server': config['jira_server'],
                'secret_folder': config['secret_folder'],
                'jira_token_file': config['token_file_path'],
                'output_base_path': config['output_base_path'],
                'viz_query': config['viz-query'],
                'postgres_log_cols': config['postgres_log_cols'],
                'insert_log_sql': config['insert_logs_sql'],
                'sprints': config['sprints'][0],
                'max_results': config['max_results'],
                'fields': config['fields'],
                'csv_settings': config['csv_settings'],
                'jira_projects': config['jira_projects'],
                'csv_headers': config['csv_headers'],
                'postgres_cols': config['postgres_cols'],
                'iris_reqs_jql': config['iris-reqs-jql'],
                'jira_project_owners': config['jira-project-owners'],
                'operational_epics': config['operational-epics']
            }

    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f'Error loading configuration file: {e}')
        raise

    # Get JIRA token
    print('Reading JIRA token from file.')
    try:
        with open(configuration['jira_token_file'], 'r') as file:
            configuration['jira_token'] = file.read().strip()

    except FileNotFoundError as e:
        print(f'Error reading JIRA token: {e}')
        raise

    return configuration'''
    
'''# Load sprint manager data from config.json into a dictionary
def load_sprint_managers(filename):
    managers = {}
    
    with open(filename, 'r') as file:
        data = json.load(file)
        
        # Assuming the JSON object under "jira-project-owners" is an array of project-owner pairs
        jira_project_owners = data.get("jira-project-owners", [])
        
        # Loop through each entry in jira-project-owners and populate the managers dictionary
        for entry in jira_project_owners:
            project = entry.get("Project")
            owner = entry.get("Owner")
            if project and owner:
                managers[project] = owner
    
    return managers'''

'''def add_sprint_owner(sprint_managers, sprint_name):
    # sprint_owners = sprint_managers
    
    for team in sprint_managers:
        if sprint_name.startswith(team):
            #manager = sprint_managers[1]
            return sprint_managers[team]
    
    return 'No Manager'
'''

'''def parse_sprint_data(sprint_string, folder_trunk):
    """Parse sprint data from the custom field format into structured data."""
    # Load the managers dictionary
    jira_helper_folder = f'{folder_trunk}helper_files/'
    jira_project_owner_file = str(jira_helper_folder) + 'config.json'

    sprint_managers = load_sprint_managers(jira_project_owner_file)

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
        return ['', '', '', '', '', '']  # Handle cases where format does not match'''

# Load operational epic data from CSV into a dictionary
'''def load_oper_epics(filename):
    epics = {}
    #filename = '/Users/wegelpi/jira/helper_files/config.json'

    # Open and load the JSON file
    with open(filename, 'r') as file:
        data = json.load(file)
        
        # Assuming 'operational-epics' is a list of dictionaries similar to the CSV rows
        operational_epics = data.get("operational-epics", [])
        
        # Loop through the list of epics and populate the dictionary
        for entry in operational_epics:
            epic = entry.get("epic")
            sprint_team = entry.get("sprint_team")
            if epic and sprint_team:
                epics[sprint_team] = epic
    
    return epics'''

'''def add_oper_epic(epic_name, folder_trunk):
    """Determine the operational epic based on the epic link."""
    # Return early if epic_name is None or empty
    if not epic_name:
        return ''  
    config_data = get_config_data()

    oper_epics = config_data['operational_epics']
    # Iterate over the dictionary, checking if any value matches or is relevant to epic_name
    for project, value in oper_epics.items():
        if value == epic_name:  # Check if the value exactly matches epic_name
            return project  # Return the project key associated with the value that matches
    
    return ''  # Return empty string if no matching value is found'''

'''def add_oper_epic(epic_name):
    """
    Determine the operational epic based on the epic link.
    
    :param epic_name: The name of the epic to look for.
    :param folder_trunk: The folder path (unused but kept for compatibility).
    :return: The sprint team associated with the epic or an empty string if no match is found.
    """
    # Return early if epic_name is None or empty
    if not epic_name:
        return ''
    
    config_data = get_config_data()

    oper_epics = config_data['operational_epics']
    # Iterate over the list of dictionaries, checking if any 'epic' matches the epic_name
    for epic_entry in oper_epics:
        if epic_entry.get("epic") == epic_name:  # Check if the 'epic' field matches
            return epic_entry.get("sprint_team", "")  # Return the associated sprint team or an empty string
    
    return ''  # Return empty string if no matching epic is found
'''
'''def triage_parser(labels):
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
        return False'''

'''def format_date(date_str):
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

def export_to_csv(csv_file):
    """Export data to a CSV file, placeholder for your actual database export logic."""
    # Your existing logic for exporting to CSV or directly to PostgreSQL
    pass'''

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

def build_jql_active(output_base_path):
    """Construct JQL query for active issues."""
    # Load the managers dictionary
    jira_helper_folder = f'{output_base_path}helper_files/'
    jira_project_owner_file = str(jira_helper_folder) + 'config.json'

    projects = load_projects(jira_project_owner_file)
    project_string = '"Compute Services", "GEMINI"'

    jql_query = f'project in ({project_string}) AND resolution = Unresolved AND Sprint IN('

    sprint_entries = [f'"{project}"' for project in projects]

    # Join all sprint entries with a comma and close the parenthesis
    jql_query += ', '.join(sprint_entries) + ')'

    return jql_query

def build_jql_completed():
    """Construct JQL query for completed issues in a specific sprint."""
    config_data = get_config_data()
    # Load the managers dictionary
    project_string = config_data['jira_projects']

    # Start building the JQL query
    jql_query = f'project in ({','.join(project_string)}) AND statusCategory = Done AND Sprint in ("{config_data['sprints']}")'

    print (f"Returning the following JQL from build_jql_completed: {jql_query}")
    return jql_query

'''def parse_component_data(components):
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
    return '|'.join(component_names)'''

'''def parse_fix_version_data(components):
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
    return '|'.join(component_names)'''

'''def parse_label_data(labels):
    """Parse label data from JIRA issue fields."""
    if not labels:
        return ''
    
    # Initialize a list to store label names
    label_names = []

    # Iterate over each label in the list
    for label in labels:
        # Ensure that label is a string, if the label structure is simple and contains direct string items
        label_names.append(str(label))  # Converts label to string if it's not already
    
    return '|'.join(label_names)'''



'''def create_connection():
    """ Create and return a PostgreSQL connection using the given connection string. """
    #config_data = get_config_data()
    #config = load_config('/Users/wegelpi/jira/helper_files/config.json')
    #secret_file = config_data['secret_folder'] + 'postgres.txt'

    with open(secret_file, 'r') as file:
        db_password = file.read().strip()

    #try:
    conn_string = f"dbname='jira_data' user='postgres' password='{db_password}' host='localhost' connect_timeout=10 sslmode='prefer'"

    conn = psycopg2.connect(conn_string)
    return conn'''

def setup_jira_client():
    #config = get_config_data()
    #config = config_data['']
    try:
        print("Setting up JIRA client...")
        options = {'server': config['jira_server']}
        file_path = str(config['secret_folder']) + 'jira-token.txt'
        with open(file_path, 'r') as file:
            jira_api_token = file.read().strip()

        jira = JIRA(options=options, token_auth=jira_api_token)

        ## Set the Authorization header on the session object directly
        jira._session.headers.update({'Authorization': f'Bearer {jira_api_token}'})
        print("JIRA client setup complete.")
        return jira
    except Exception as e:
        print(f"Failed to initialize JIRA client: {e}")
        return None

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

def compdiv_initiatives():
    """
    Update the Compute Division initiatives table in PostgreSQL (tbl_jira_initiatives) 
    with JIRA issues matching the JQL query.
    """

    # JQL Query to fetch initiatives
    jql = 'project = "C-ing Stars" AND labels in (compdiv-initiative-2025) ORDER BY summary ASC'
    print ("Querying JIRA to update Compute Division initiatives list...")

    jira = setup_jira_client()
    if jira is None:
        raise Exception("Failed to initialize JIRA client. Check configuration and credentials.")
    print ("JIRA client initialized successfully.")

    # Fetch initiatives from JIRA
    initiatives = fetch_issues(jira, jql)
    print (f"Fetched {len(initiatives)} initiatives from JIRA.")

    # Connect to PostgreSQL database
    conn = create_connection()
    if conn is None:
        raise Exception("Failed to connect to the PostgreSQL database.")
    print ("Database connection established successfully.")

    try:
        cursor = conn.cursor()

        # Query to check if issue_key already exists
        existing_keys_query = "SELECT issue_key FROM tbl_jira_initiatives"
        cursor.execute(existing_keys_query)
        existing_keys = set(row[0] for row in cursor.fetchall())
        print (f"Fetched {len(existing_keys)} existing issue keys from the database.")

        # Prepare data for insertion
        new_initiatives = []
        for issue in initiatives:
            if issue.key not in existing_keys:
                fields = issue.fields
                labels = '|'.join(fields.labels) if getattr(fields, 'labels', []) else ''  # Handle labels

                new_initiatives.append((
                    issue.key,
                    fields.summary,
                    getattr(fields, 'customfield_10002', 0),  # Example: Story Points or custom field
                    fields.status.name,
                    fields.issuetype.name,
                    labels
                ))
                print (f"New issue to add: {issue.key} - {fields.summary}")

        # Insert new initiatives into the database
        if new_initiatives:
            insert_query = """
                INSERT INTO tbl_jira_initiatives (issue_key, summary, story_points, status, issue_type, labels)
                VALUES %s
            """
            execute_values(cursor, insert_query, new_initiatives)
            conn.commit()
            print (f"Inserted {len(new_initiatives)} new initiatives into tbl_jira_initiatives.")
        else:
            print ("No new initiatives to insert.")

    except Exception as e:
        print (f"An error occurred: {e}")
        conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            print ("Database connection closed.")


    '''
    Append new initiatives to Postgres. If no new initiatives exist then don't do anything
    '''

'''def jira_obj_isrelated(issue_key):
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
'''