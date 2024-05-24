#JQL builder
import csv

def build_jql_active():
    # Load the managers dictionary
    jira_helper_folder = '/Users/wegelpi/jira/helper_files/'
    jira_project_owner_file = str(jira_helper_folder) + 'jira-projects-owners.csv'
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

def build_jql_completed(sprint):

    # Load the managers dictionary
    jira_helper_folder = '/Users/wegelpi/jira/helper_files/'
    jira_project_owner_file = str(jira_helper_folder) + 'jira-projects-owners.csv'
    #jira_projects = load_projects(jira_project_owner_file)

    projects = load_projects(jira_project_owner_file)
    project_string = '"Compute Services", "GEMINI"'

    # Start building the JQL query
    jql_query = f'project in ({project_string}) AND status = "Accepted and Close(Q)" AND Sprint in ('

    sprint_entries = [f'"{project} {sprint}"' for project in projects]

    # Join all sprint entries with a comma and close the parenthesis
    jql_query += ', '.join(sprint_entries) + ')'

    #print(jql_query)
    
    return jql_query

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
    return projects

if __name__ == "__main__":
    build_jql_completed('2024.05')