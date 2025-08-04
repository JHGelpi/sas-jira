import os
from jira import JIRA
from dotenv import load_dotenv
import sys

# Load environment variables from a .env file
load_dotenv()

# --- Configuration ---
JIRA_SERVER = os.getenv("JIRA_SERVER")
JQL_QUERY = os.getenv("JQL_QUERY")
LABEL_TO_ADD = os.getenv("LABEL_TO_ADD")
#LABEL_IGNORE = os.getenv("LABEL_IGNORE")
COMMENT_TO_ADD = os.getenv("COMMENT_TO_ADD")
COMMENT_TO_ADD_ICEBOX = os.getenv("COMMENT_TO_ADD_ICEBOX")

def setup_jira_client():
    JIRA_SERVER = os.getenv("JIRA_SERVER")
    JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")

    jira = JIRA(
        server=JIRA_SERVER,
        token_auth=JIRA_API_TOKEN
    )

    ## Set the Authorization header on the session object directly
    jira._session.headers.update({'Authorization': f'Bearer {JIRA_API_TOKEN}'})

    return jira

# --- Main Logic ---
def update_issues():
    """
    Connects to Jira, finds stale issues, and updates them.
    """
    if not all([JQL_QUERY]):
        print("❌ Error: Missing one or more required environment variables.")
        sys.exit(1)

    print(f"⚙️ Connecting to Jira server at {JIRA_SERVER}...")

    try:
        jira_client = setup_jira_client()
        
        # Verify connection by getting server info
        server_info = jira_client.server_info()
        print(f"✅ Successfully connected to Jira version {server_info['version']}!")

    except Exception as e:
        print(f"❌ Failed to connect to Jira: {e}")
        sys.exit(1)


    print(f"🔍 Running JQL query to find stale issues...")
    print(f"   Query: {JQL_QUERY}")

    try:
        stale_issues = jira_client.search_issues(JQL_QUERY, maxResults=False)
        
        if not stale_issues:
            print("🎉 No stale issues found. Exiting.")
            return

        print(f" found {len(stale_issues)} issues to process.")

        for issue in stale_issues:
            print(f"   -> Processing issue {issue.key}: {issue.fields.summary}")

            # Add the label if it doesn't already exist
            if LABEL_TO_ADD and LABEL_TO_ADD not in issue.fields.labels:
                new_labels = issue.fields.labels + [LABEL_TO_ADD]
                issue.update(fields={"labels": new_labels})
                print(f"      🏷️  Added label: '{LABEL_TO_ADD}'")
            elif LABEL_TO_ADD:
                 print(f"      🏷️  Label '{LABEL_TO_ADD}' already exists. Skipping.")

            # Add the comment
            if COMMENT_TO_ADD:
                jira_client.add_comment(issue, COMMENT_TO_ADD)
                print(f"      💬 Added automated comment.")

            print(f"✅ {issue.key} update completed...")

        print("\n✨ Automation complete!")

    except Exception as e:
        print(f"❌ An error occurred during issue processing: {e}")
        sys.exit(1)

def close_icebox_issues():
    # Close issues that still have the icebox label
    JQL_QUERY_ICEBOX = os.getenv("JQL_QUERY_ICEBOX")
    if not JQL_QUERY_ICEBOX:
        print("❌ Error: Missing JQL_QUERY_ICEBOX environment variable.")
        sys.exit(1)

    print(f"⚙️ Connecting to Jira server at {JIRA_SERVER}...")

    try:
        jira_client = setup_jira_client()
        
        # Verify connection by getting server info
        server_info = jira_client.server_info()
        print(f"✅ Successfully connected to Jira version {server_info['version']}!")

    except Exception as e:
        print(f"❌ Failed to connect to Jira: {e}")
        sys.exit(1)

    print(f"🔍 Running JQL query to find icebox issues...")
    print(f"   Query: {JQL_QUERY_ICEBOX}")

    try:
        icebox_issues = jira_client.search_issues(JQL_QUERY_ICEBOX, maxResults=False)

        if not icebox_issues:
            print("🎉 No icebox issues found. Exiting.")
            return

        print(f" found {len(icebox_issues)} issues to process.")

        for issue in icebox_issues:
            print(f"   -> Processing issue {issue.key}: {issue.fields.summary}")

            # Close the issue
            issue.transition("Done")
            print(f"      ✅ Closed issue {issue.key}")

            # Add the comment
            if COMMENT_TO_ADD_ICEBOX:
                jira_client.add_comment(issue, COMMENT_TO_ADD_ICEBOX)
                print(f"      💬 Added automated comment.")

        print("\n✨ Automation complete!")

    except Exception as e:
        print(f"❌ An error occurred during issue processing: {e}")
        sys.exit(1)

def main():
    update_issues()
    close_icebox_issues()

if __name__ == "__main__":
    main()