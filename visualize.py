#import plotly_chart
import pandas as pd
import plotly.express as px
from datetime import datetime
import psycopg2
#from psycopg2 import sql

def create_connection():
    """ Create and return a PostgreSQL connection using the given connection string. """
    config_file = '/Users/wegelpi/encrypt/secrets/postgres.txt'
    with open(config_file, 'r') as file:
        db_password = file.read().strip()

    conn_string = f"dbname='jira_data' user='postgres' password='{db_password}' host='localhost' connect_timeout=10 sslmode='prefer'"
    conn = psycopg2.connect(conn_string)
    return conn

# Function to fetch data
def fetch_data(query):
    conn = create_connection()
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# SQL query to fetch data
file_path = '/Users/wegelpi/jira/helper_files/viz_query.txt'

with open(file_path, 'r') as file:
    sql_query = file.read().strip()

# Fetching the data
data = fetch_data(sql_query)

# Plotting
fig = px.bar(data, x='sprint_name', y='issue_count', color='issue_type', title='Count of Issues by Type')
fig.show()

# Concatenating 'issue_type' and 'start_date' for hover_name with additional formatting for clarity
data['hover_info'] = data['issue_type'] + ' - ' + data['sprint_name'].astype(str)

# Now, use the new 'hover_info' column for the hover_name in your pie chart
fig = px.pie(data, values='issue_count', hover_name='hover_info',)
fig.show()