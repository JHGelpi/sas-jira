import csv
from datetime import datetime
import json
import psycopg2

# Load sprint manager data from config.json into a dictionary
def load_sprint_managers(filename):
    managers = {}
    #filename = '/Users/wegelpi/jira/helper_files/config.json'
    
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
    
    return managers
""" 
def load_sprint_managers():
    managers = {}
    filename = '/Users/wegelpi/jira/helper_files/config.json'
    with open(filename, 'r') as file:
        data = json.load(file)
    
    managers = data.get("jira-project-owners")
    return managers

    with open(filename, mode='r', encoding='utf-8') as file:
        reader = csv.reader(file)
        next(reader)  # Skip the header row if there is one
        for row in reader:
            if len(row) >= 2:
                sprint_name, manager = row[0].strip(), row[1].strip()
                managers[sprint_name] = manager
    return managers
"""

def load_config(path):
    """Load configuration from a JSON file."""
    with open(path, 'r') as file:
        return json.load(file)

def add_sprint_owner(sprint_managers, sprint_name):
    # sprint_owners = sprint_managers
    
    for team in sprint_managers:
        if sprint_name.startswith(team):
            #manager = sprint_managers[1]
            return sprint_managers[team]
    
    return 'No Manager'

def parse_sprint_data(sprint_string, folder_trunk):
    """Parse sprint data from the custom field format into structured data."""
    # Load the managers dictionary
    jira_helper_folder = f'{folder_trunk}helper_files/'
    #jira_project_owner_file = str(jira_helper_folder) + 'jira-projects-owners.csv'
    jira_project_owner_file = str(jira_helper_folder) + 'config.json'
    #jira_oper_epics = jira_helper_folder & 'operational-epics.csv'

    sprint_managers = load_sprint_managers(jira_project_owner_file)
    #oper_epics = load_oper_epics(jira_oper_epics)

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

# Load operational epic data from CSV into a dictionary
def load_oper_epics(filename):
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
    
    return epics
"""
def load_oper_epics(filename):
    epics = {}
    with open(filename, mode='r', encoding='utf-8') as file:
        reader = csv.reader(file)
        next(reader)  # Skip the header row if there is one
        for row in reader:
            if len(row) >= 2:
                epic, sprint_team = row[0].strip(), row[1].strip()
                epics[sprint_team] = epic
    return epics
"""
def add_oper_epic(epic_name, folder_trunk):
    """Determine the operational epic based on the epic link."""
    # Return early if epic_name is None or empty
    if not epic_name:
        return ''  

    jira_helper_folder = f'{folder_trunk}helper_files/'
    #jira_oper_epics = str(jira_helper_folder) + 'operational-epics.csv'
    jira_oper_epics = str(jira_helper_folder) + 'config.json'
    oper_epics = load_oper_epics(jira_oper_epics)

    # Iterate over the dictionary, checking if any value matches or is relevant to epic_name
    for project, value in oper_epics.items():
        if value == epic_name:  # Check if the value exactly matches epic_name
            return project  # Return the project key associated with the value that matches
    
    return ''  # Return empty string if no matching value is found

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
        #return datetime.strptime('1900-12-12 12:00:00', '%Y-%m-%dT%H:%M:%S.%f%z')  # Return '' or any other suitable placeholder
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
    pass

# Load sprint manager data from JSON into a list of project names
def load_projects(filename):
    projects = []
    with open(filename, mode='r', encoding='utf-8') as file:
        data = json.load(file)
        # Access the list of projects under the key 'jira-project-owners'
        for item in data.get("jira-project-owners", []):
            project_name = item.get("Project", "").strip()
            if project_name:  # Check if project_name is not empty
                projects.append(project_name)
    return projects
"""
# Load sprint manager data from CSV into a dictionary
def load_projects(filename):
    projects = []
    with open(filename, mode='r', encoding='utf-8') as file:
        reader = csv.reader(file)
        next(reader)  # Skip the header row if there is one
        for row in reader:
            if len(row) >= 1:
                project_name = row[0].strip()
                projects.append(project_name)
    return projects"""

def build_jql_active(output_base_path):
    """Construct JQL query for active issues."""
    # Load the managers dictionary
    jira_helper_folder = f'{output_base_path}helper_files/'
    #jira_project_owner_file = str(jira_helper_folder) + 'jira-projects-owners.csv'
    jira_project_owner_file = str(jira_helper_folder) + 'config.json'
    #jira_projects = load_projects(jira_project_owner_file)

    projects = load_projects(jira_project_owner_file)
    project_string = '"Compute Services", "GEMINI"'

    jql_query = f'project in ({project_string}) AND resolution = Unresolved AND Sprint IN('

    sprint_entries = [f'"{project}"' for project in projects]

    # Join all sprint entries with a comma and close the parenthesis
    jql_query += ', '.join(sprint_entries) + ')'

    #print (jql_query)
    #print (jql_query)

    return jql_query

def build_jql_completed(sprint, folder_trunk):
    """Construct JQL query for completed issues in a specific sprint."""
    # Load the managers dictionary
    jira_helper_folder = f'{folder_trunk}helper_files/'
    #jira_project_owner_file = str(jira_helper_folder) + 'jira-projects-owners.csv'
    jira_project_owner_file = str(jira_helper_folder) + 'config.json'
    #jira_projects = load_projects(jira_project_owner_file)

    projects = load_projects(jira_project_owner_file)
    project_string = '"Compute Services", "GEMINI"'

    # Start building the JQL query
    jql_query = f'project in ({project_string}) AND status = "Accepted and Close(Q)" AND Sprint in ('

    #sprint_entries = [f'"{project} {sprint}"' for project in projects]
    sprint_entries = [f'"{sprint}"']

    # Join all sprint entries with a comma and close the parenthesis
    jql_query += ', '.join(sprint_entries) + ')'
    #print (jql_query)
    return jql_query

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
            #cursor.copy_expert(f"COPY tbl_jira_sprint_data ({','.join(postgres_cols)}) FROM STDIN WITH CSV HEADER DELIMITER ',' QUOTE '\"'", f)
            if tbl_flag == 'hist':
                sql_query = f"""
                    COPY tbl_jira_sprint_data ({','.join(postgres_cols)})
                    FROM STDIN WITH CSV HEADER DELIMITER ',' QUOTE '\"' NULL 'NULL'
                    """
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

def create_connection():
    """ Create and return a PostgreSQL connection using the given connection string. """
    config = load_config('/Users/wegelpi/jira/helper_files/config.json')
    secret_file = config['secret_folder'] + 'postgres.txt'

    with open(secret_file, 'r') as file:
        db_password = file.read().strip()

    #try:
    conn_string = f"dbname='jira_data' user='postgres' password='{db_password}' host='localhost' connect_timeout=10 sslmode='prefer'"
    #conn = psycopg2.connect("dbname='jira_data' user='postgres' password='password' host='localhost' connect_timeout=10 sslmode='prefer'")
    #print (conn_string)
    conn = psycopg2.connect(conn_string)
    return conn
