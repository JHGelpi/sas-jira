import os
from jira import JIRA
from dotenv import load_dotenv
import logging
from datetime import datetime, timedelta
import csv
from collections import defaultdict
import json
import re

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

def _extract_json_from_string(text: str) -> dict | None:
    """
    Finds and extracts a JSON object from a complex string by matching curly braces.
    """
    try:
        # Find the start of the JSON object within the larger string
        start_brace_index = text.find('{')
        if start_brace_index == -1:
            return None

        open_braces = 0
        # Iterate through the string to find the matching closing brace
        for i, char in enumerate(text[start_brace_index:]):
            if char == '{':
                open_braces += 1
            elif char == '}':
                open_braces -= 1
            
            if open_braces == 0:
                # We've found the end of the JSON object
                json_string = text[start_brace_index : start_brace_index + i + 1]
                return json.loads(json_string)
        return None
    except (json.JSONDecodeError, IndexError):
        return None


def get_daily_push_report(jira):
    """
    Finds all tickets with commits or merged pull requests in the last N days
    and generates a CSV report.
    """
    # Get configuration from environment variables
    projects = os.getenv('JIRA_PROJECTS', '')
    if not projects:
        logger.error("❌ JIRA_PROJECTS environment variable is not set. Aborting.")
        return

    days_to_check = os.getenv('JIRA_PUSH_REPORT_DAYS', '7')
    report_dir = os.getenv('JIRA_REPORT_DIR', './reports')
    os.makedirs(report_dir, exist_ok=True)

    jql_query = f"project in ({projects}) AND type in (Story, Bug) AND updated >= -{days_to_check}d AND (Development[pullrequests].status IS NOT EMPTY)"


    logger.info(f"🔍 Running JQL query to find tickets with recent development activity...")
    logger.info(f"   Query: {jql_query}")

    try:
        # We don't need to expand 'development' if the data is in a custom field
        issues = jira.search_issues(jql_query, maxResults=1000)
        
        if not issues:
            logger.info(f"🎉 No tickets with PR activity found in the last {days_to_check} days.")
            return

        logger.info(f"Found {len(issues)} tickets with PR activity. Analyzing summary data...")
        
        activities = []
        time_window = datetime.now(datetime.now().astimezone().tzinfo) - timedelta(days=int(days_to_check))

        for issue in issues:
            dev_summary_string = issue.raw['fields'].get('customfield_13100')
            if not dev_summary_string:
                continue

            # --- NEW LOGIC: Use a robust function to extract the JSON ---
            match = re.search(r"devSummaryJson=(.*)", dev_summary_string)
            if not match:
                continue
            
            json_substring = match.group(1)
            dev_summary_json = _extract_json_from_string(json_substring)

            if not dev_summary_json:
                logger.warning(f"Could not parse development summary for {issue.key}. Skipping.")
                continue

            try:
                pr_summary = dev_summary_json.get('cachedValue', {}).get('summary', {}).get('pullrequest', {}).get('overall', {})

                if not pr_summary:
                    continue

                last_updated_str = pr_summary.get('lastUpdated')
                merged_count = pr_summary.get('details', {}).get('mergedCount', 0)

                if last_updated_str and merged_count > 0:
                    pr_update_time = datetime.strptime(last_updated_str, '%Y-%m-%dT%H:%M:%S.%f%z')
                    
                    if pr_update_time >= time_window:
                        logger.info(f"  -> Found recent merged PR activity for {issue.key}")
                        activities.append({
                            'type': 'Pull Request (Activity)',
                            'repo': 'N/A (Summary)',
                            'branch': 'N/A (Summary)',
                            'ticket': issue.key,
                            'summary': issue.fields.summary,
                            'author': 'N/A (Summary)',
                            'timestamp': last_updated_str,
                            'message': f"{merged_count} merged PR(s) associated with this ticket.",
                            'url': f"https://rndjira.sas.com/browse/{issue.key}"
                        })

            except (ValueError, KeyError) as e:
                logger.warning(f"Could not process parsed summary for {issue.key}. Skipping. Error: {e}")


        if not activities:
            logger.info(f"🎉 No recent merged PR activity found within the last {days_to_check} days based on summary data.")
            return

        # Generate the CSV report
        today_str = datetime.now().strftime('%Y-%m-%d')
        report_path = os.path.join(report_dir, f"daily_push_report_{today_str}.csv")
        
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        
        with open(report_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Timestamp', 'Activity Type', 'Repository', 'Branch', 'Ticket', 'Summary', 'Author', 'Message/Title', 'URL'])
            
            for act in activities:
                writer.writerow([
                    act['timestamp'], act['type'], act['repo'], act['branch'],
                    act['ticket'], act['summary'], act['author'], act['message'], act['url']
                ])
        
        logger.info(f"✅ Successfully generated daily push report with {len(activities)} activities at: {report_path}")

    except Exception as e:
        logger.error(f"❌ An error occurred while generating the report: {e}")
        if 'issue' in locals():
            logger.debug(f"Raw data for potentially problematic issue {issue.key}: {json.dumps(issue.raw, indent=2)}")


def main():
    """Main function to execute the daily push report."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(dotenv_path=os.path.join(project_root, '.env'))
    
    jira_client = connect_to_jira()
    if jira_client:
        get_daily_push_report(jira_client)

if __name__ == "__main__":
    main()
