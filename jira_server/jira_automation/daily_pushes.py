import os
from jira import JIRA
from dotenv import load_dotenv
import logging
from datetime import datetime, timedelta
import csv
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def connect_to_jira():
    """Connects to Jira using credentials from environment variables."""
    try:
        logger.info(f"⚙️ Connecting to Jira server at {os.getenv('JIRA_URL')}...")
        jira_client = JIRA(
            server=os.getenv('JIRA_URL'),
            token_auth=os.getenv('JIRA_TOKEN')
        )
        logger.info(f"✅ Successfully connected to Jira version {jira_client.server_info()['version']}!")
        return jira_client
    except Exception as e:
        logger.error(f"❌ Failed to connect to Jira: {e}")
        return None

def get_daily_push_report(jira):
    """
    Finds all tickets with commits in the last 24 hours and generates a report.
    """
    # Get configuration from environment variables
    projects = os.getenv('JIRA_PROJECTS', '')
    if not projects:
        logger.error("❌ JIRA_PROJECTS environment variable is not set. Aborting.")
        return

    report_dir = os.getenv('JIRA_REPORT_DIR', './reports')
    os.makedirs(report_dir, exist_ok=True) # Ensure the report directory exists
    
    # We look for issues updated in the last day. A commit will trigger an update.
    jql_query = f"project in ({projects}) AND updated >= -1d"

    logger.info("🔍 Running JQL query to find tickets with recent activity...")
    logger.info(f"   Query: {jql_query}")

    try:
        # We need to expand the 'development' field to get commit data.
        # This is a special, internal field and might require specific permissions.
        issues = jira.search_issues(jql_query, maxResults=500, expand="development")
        
        if not issues:
            logger.info("🎉 No tickets with development activity found in the last 24 hours.")
            return

        logger.info(f"Found {len(issues)} tickets with recent activity. Analyzing for pushes...")
        
        # Group commits by repository and branch
        pushes = defaultdict(list)
        
        for issue in issues:
            # The development information is often in a raw, non-standard field.
            # We check for 'dev-status' which is a common internal API field name.
            if hasattr(issue.raw['fields'], 'dev-status'):
                dev_info = issue.raw['fields']['dev-status']
                # The structure can vary, so we check for the 'detail' key
                if 'detail' in dev_info and dev_info['detail']:
                    for detail in dev_info['detail']:
                        if 'commits' in detail:
                            for commit in detail['commits']:
                                # Filter commits to only include those from the last 24 hours
                                commit_time = datetime.strptime(commit['authorTimestamp'], '%Y-%m-%dT%H:%M:%S.%f%z')
                                if commit_time >= (datetime.now(commit_time.tzinfo) - timedelta(days=1)):
                                    repo_name = detail.get('name', 'Unknown Repo')
                                    branch_name = commit.get('branch', 'Unknown Branch')
                                    
                                    pushes[(repo_name, branch_name)].append({
                                        'ticket': issue.key,
                                        'summary': issue.fields.summary,
                                        'author': commit['author']['name'],
                                        'timestamp': commit['authorTimestamp'],
                                        'message': commit['message'].strip(),
                                        'commit_url': commit.get('url', 'N/A')
                                    })

        if not pushes:
            logger.info("🎉 No new pushes found within the last 24 hours.")
            return

        # Generate the CSV report
        today_str = datetime.now().strftime('%Y-%m-%d')
        report_path = os.path.join(report_dir, f"daily_push_report_{today_str}.csv")
        
        with open(report_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Repository', 'Branch', 'Ticket', 'Summary', 'Author', 'Timestamp', 'Commit Message', 'URL'])
            
            for (repo, branch), commits in sorted(pushes.items()):
                for commit in sorted(commits, key=lambda x: x['timestamp']):
                    writer.writerow([
                        repo, branch, commit['ticket'], commit['summary'],
                        commit['author'], commit['timestamp'], commit['message'], commit['commit_url']
                    ])
        
        logger.info(f"✅ Successfully generated daily push report at: {report_path}")

    except Exception as e:
        logger.error(f"❌ An error occurred while generating the report: {e}")


def main():
    """Main function to execute the daily push report."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(dotenv_path=os.path.join(project_root, '.env'))
    
    jira_client = connect_to_jira()
    if jira_client:
        get_daily_push_report(jira_client)

if __name__ == "__main__":
    main()
