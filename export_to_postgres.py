#export_to_postgres
import psycopg2
from psycopg2 import sql

'''def load_config():
    """ Load the connection string from a config file. """
    config_file = '/Users/wegelpi/encrypt/secrets/postgres.txt'

    try:
        with open(config_file, 'r') as file:
            return file.read().strip()
    except FileNotFoundError:
        print("Configuration file not found.")
        return None'''

def create_connection():
    """ Create and return a PostgreSQL connection using the given connection string. """
    config_file = '/Users/wegelpi/encrypt/secrets/postgres.txt'
    with open(config_file, 'r') as file:
        db_password = file.read().strip()

    #try:
    conn_string = f"dbname='jira_data' user='postgres' password='{db_password}' host='localhost' connect_timeout=10 sslmode='prefer'"
    #conn = psycopg2.connect("dbname='jira_data' user='postgres' password='password' host='localhost' connect_timeout=10 sslmode='prefer'")
    print (conn_string)
    conn = psycopg2.connect(conn_string)
    return conn
    #except psycopg2.OperationalError as e:
        #print(f"Connection error: {e}")
        #return None
def load_columns(config_file):
    with open(config_file, 'r') as file:
        # Read the entire line, remove any surrounding whitespace or newlines
        line = file.read().strip()
        # Strip outer single quotes and split the string into a list by "','"
        # This splits correctly assuming the format is like 'col1','col2','col3'
        columns = line.strip("'").split("','")
    return tuple(columns)  # Convert list to tuple for psycopg2 compatibility

def append_csv(csv_file):
    conn = None
    cursor = None

    conn = create_connection()
    if conn is None:
        return
    
    # Connect to JIRA
    #file_path = '/Users/wegelpi/encrypt/secrets/postgres.txt'
    config_file = '/Users/wegelpi/jira/helper_files/postgres_columns.txt'

   #try:
    with open(config_file, 'r') as file:
        line = file.read().strip()
        postgres_cols = line.strip("'").split("','")
    #load_config()

    #with open(file_path, 'r') as file:
    #    postgres_conn_string = file.read().strip()

    #print(postgres_conn_string)

    #conn = psycopg2.connect(postgres_conn_string)
    postgres_cols = load_columns(config_file)

    with open(csv_file, 'r', newline='', encoding='utf-8') as f:
        next(f)  # Skip header
        cursor = conn.cursor()
        cursor.copy_expert(f"COPY tbl_jira_sprint_data ({','.join(postgres_cols)}) FROM STDIN WITH CSV HEADER DELIMITER ',' QUOTE '\"'", f)
        conn.commit()
        cursor.close()
        print(f"Data appended successfully from {csv_file}")

   #except Exception as e:
        #print("Error:", e)
        #conn.rollback()  # rollback if any exception occurred

   #finally:
    # Closing the connection
    if cursor:
        cursor.close()  # Close the cursor
    if conn:
        conn.close()  # Close the database connection

if __name__ == "__main__":
    append_csv('/Users/wegelpi/jira/jira-output-20240516121437.csv')




'''cursor = conn.cursor()
    with open(csv_file, 'r') as f:
        next(f)
        cursor.copy_from(f, 'tbl_jira_sprint_data', sep=',', columns=(postgres_cols))
        conn.commit()
        print(f"Data appended successfully from {csv_file}")'''