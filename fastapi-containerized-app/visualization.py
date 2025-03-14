import pandas as pd
import matplotlib.pyplot as plt
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def scatter_plot():

    # Database connection parameters
    db_password = os.getenv('DB_PASSWORD')
    db_user = os.getenv('DB_USER')
    db_name = os.getenv('DB_NAME')
    db_host = os.getenv('DB_HOST')
    db_timeout = os.getenv('DB_CONN_TIMEOUT')

    # Create a connection to the PostgreSQL database
    conn_string = f"dbname='{db_name}' user='{db_user}' password='{db_password}' host='{db_host}' connect_timeout={db_timeout} sslmode='prefer'"
    conn = psycopg2.connect(conn_string)

    # SQL query to extract data
    sql_query = sql_statement()
    # Read the data into a DataFrame
    df = pd.read_sql_query(sql_query, conn)

    # Close the database connection
    conn.close()

    # Generate a scatter plot
    x_column = 'resolution_time_days'  # Replace with the name of the column for the x-axis
    y_column = 'resolution_time_days'  # Replace with the name of the column for the y-axis

    plt.figure(figsize=(10, 6))
    plt.scatter(df[x_column], df[y_column])

    # Add data point labels
    for i, txt in enumerate(df['issue_key']):
        plt.annotate(txt, (df[x_column][i], df[y_column][i]), fontsize=8, alpha=0.7)

    plt.xlabel(x_column)
    plt.ylabel(y_column)
    plt.title('Scatter Plot')

    # Calculate percentiles
    percentile_10 = df['resolution_time_days'].quantile(0.10)
    percentile_90 = df['resolution_time_days'].quantile(0.90)

    # Generate a histogram
    plt.figure(figsize=(10, 6))
    plt.hist(df['resolution_time_days'], bins=20, edgecolor='black', alpha=0.7)
    plt.axvline(percentile_10, color='r', linestyle='dashed', linewidth=1, label='10th Percentile')
    plt.axvline(percentile_90, color='g', linestyle='dashed', linewidth=1, label='90th Percentile')
    plt.xlabel('Resolution Time (Days)')
    plt.ylabel('Frequency')
    plt.title('Histogram of Resolution Time for Bugs')
    plt.legend()

    # Generate a box and whisker plot
    plt.figure(figsize=(10, 6))
    box = plt.boxplot(df['resolution_time_days'], vert=False, patch_artist=True)
    plt.xlabel('Resolution Time (Days)')
    plt.title('Box and Whisker Plot of Resolution Time for Bugs')

    # Adding labels for the boundaries/outliers
    whiskers = [item.get_xdata() for item in box['whiskers']]
    caps = [item.get_xdata() for item in box['caps']]
    fliers = [item.get_xdata() for item in box['fliers']]
    medians = [item.get_xdata() for item in box['medians']]
    boxes = [item.get_path().vertices[:, 0] for item in box['boxes']]

    for whisker in whiskers:
        plt.annotate(f'{whisker[1]:.2f}', xy=(whisker[1], 1), xytext=(whisker[1], 1.05),
                     arrowprops=dict(facecolor='black', shrink=0.05), fontsize=8, ha='center')

    for cap in caps:
        plt.annotate(f'{cap[1]:.2f}', xy=(cap[1], 1), xytext=(cap[1], 1.05),
                     arrowprops=dict(facecolor='black', shrink=0.05), fontsize=8, ha='center')

    for flier in fliers:
        for outlier in flier:
            plt.annotate(f'{outlier:.2f}', xy=(outlier, 1), xytext=(outlier, 1.05),
                         arrowprops=dict(facecolor='red', shrink=0.05), fontsize=8, ha='center')

    for median in medians:
        plt.annotate(f'{median[0]:.2f}', xy=(median[0], 1), xytext=(median[0], 1.05),
                     arrowprops=dict(facecolor='blue', shrink=0.05), fontsize=8, ha='center')

    for box in boxes:
        q1 = box[0]
        plt.annotate(f'{q1:.2f}', xy=(q1, 1), xytext=(q1, 1.05),
                     arrowprops=dict(facecolor='green', shrink=0.05), fontsize=8, ha='center')

    # Show all plots
    plt.show()

def box_whisker():

    #load_dotenv()

    # Database connection parameters
    db_password = os.getenv('DB_PASSWORD')
    db_user = os.getenv('DB_USER')
    db_name = os.getenv('DB_NAME')
    db_host = os.getenv('DB_HOST')
    db_timeout = os.getenv('DB_CONN_TIMEOUT')

    # Create a connection to the PostgreSQL database
    conn_string = f"dbname='{db_name}' user='{db_user}' password='{db_password}' host='{db_host}' connect_timeout={db_timeout} sslmode='prefer'"
    conn = psycopg2.connect(conn_string)

    # SQL query to extract data
    sql_query = sql_statement()
    # Read the data into a DataFrame
    df = pd.read_sql_query(sql_query, conn)

    # Close the database connection
    conn.close()

    # Generate a box and whisker plot
    plt.figure(figsize=(10, 6))
    plt.boxplot(df['resolution_time_days'], vert=False)
    plt.xlabel('Resolution Time (Days)')
    plt.title('Box and Whisker Plot of Resolution Time for Bugs')
    plt.show()

def histogram():

    #load_dotenv()

    # Database connection parameters
    db_password = os.getenv('DB_PASSWORD')
    db_user = os.getenv('DB_USER')
    db_name = os.getenv('DB_NAME')
    db_host = os.getenv('DB_HOST')
    db_timeout = os.getenv('DB_CONN_TIMEOUT')

    # Create a connection to the PostgreSQL database
    conn_string = f"dbname='{db_name}' user='{db_user}' password='{db_password}' host='{db_host}' connect_timeout={db_timeout} sslmode='prefer'"
    conn = psycopg2.connect(conn_string)

    # SQL query to extract data
    sql_query = sql_statement()
    # Read the data into a DataFrame
    df = pd.read_sql_query(sql_query, conn)

    # Close the database connection
    conn.close()

    # Calculate percentiles
    percentile_10 = df['resolution_time_days'].quantile(0.10)
    percentile_90 = df['resolution_time_days'].quantile(0.90)

    # Generate a histogram
    plt.figure(figsize=(10, 6))
    plt.hist(df['resolution_time_days'], bins=20, edgecolor='black', alpha=0.7)
    plt.axvline(percentile_10, color='r', linestyle='dashed', linewidth=1, label='10th Percentile')
    plt.axvline(percentile_90, color='g', linestyle='dashed', linewidth=1, label='90th Percentile')
    plt.xlabel('Resolution Time (Days)')
    plt.ylabel('Frequency')
    plt.title('Histogram of Resolution Time for Bugs')
    plt.legend()
    plt.show()

def sql_statement():
    sql_query = """
    select a.issue_key,
        a.jira_created_date,
        a.jira_updated_date,
        a.sprint_name,
        EXTRACT(DAY FROM (DATE_TRUNC('day', a.jira_updated_date) - DATE_TRUNC('day', a.jira_created_date))) AS resolution_time_days
    from public.tbl_jira_sprint_data a
    where a.issue_status in('Closed', 'Accepted and Close(Q)')
    and a.issue_type = 'Bug'
    and a.escaped_bug_flag = 'Y'
    and a.sprint_name like '%2025.%'
    and a.jira_created_date is not null
    ;
    """

    return sql_query

# Main function
def main():
    scatter_plot()
    #box_whisker()
    #histogram()

if __name__ == "__main__":
    main()