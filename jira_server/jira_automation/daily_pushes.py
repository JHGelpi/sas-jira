# jira_automation/daily_pushes.py
"""
Daily push report generation.

This module tracks merged pull requests and generates an HTML report with charts
showing development activity over time.
"""

import os
from jira import JIRA
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json
import re
import pandas as pd
import plotly.express as px
import shutil
from logging_utils import get_logger, log_section_header

logger = get_logger(__name__)


def connect_to_jira():
    """Connects to Jira using credentials from environment variables."""
    try:
        jira_url = os.getenv('JIRA_URL')
        logger.connecting(f"Connecting to Jira server at {jira_url}")
        
        jira_client = JIRA(
            server=jira_url,
            token_auth=os.getenv('JIRA_TOKEN')
        )
        
        version = jira_client.server_info()['version']
        logger.success(f"Connected to Jira version {version}")
        return jira_client
        
    except Exception as e:
        logger.error(f"Failed to connect to Jira: {e}")
        return None


def _extract_json_from_string(text: str) -> dict | None:
    """
    Finds and extracts a JSON object from a complex string by matching curly braces.
    """
    try:
        start_brace_index = text.find('{')
        if start_brace_index == -1:
            return None

        open_braces = 0
        for i, char in enumerate(text[start_brace_index:]):
            if char == '{':
                open_braces += 1
            elif char == '}':
                open_braces -= 1
            
            if open_braces == 0:
                json_string = text[start_brace_index : start_brace_index + i + 1]
                return json.loads(json_string)
        return None
    except (json.JSONDecodeError, IndexError):
        return None


def generate_html_report(activities: list, report_path: str, days: str, report_dir: str):
    """Generates a self-contained HTML report with a chart and a data table."""
    logger.processing("Generating HTML report")
    
    if not activities:
        logger.info("No activities to report")
        return

    # Convert data to a Pandas DataFrame for easy manipulation
    df = pd.DataFrame(activities)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['date'] = df['timestamp'].dt.date

    # Aggregate data for the chart: count of PRs per day
    daily_counts = df.groupby('date').size().reset_index(name='count')
    daily_counts = daily_counts.sort_values('date')

    refresh_time = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
    chart_title = f'Merged Pull Request Activity (Last {days} Days)'
    
    # Create a bar chart with Plotly
    fig = px.bar(
        daily_counts,
        x='date',
        y='count',
        title=chart_title,
        labels={'date': 'Date', 'count': 'Number of Merged PRs'}
    )
    fig.update_layout(xaxis_title="Date", yaxis_title="Count")
    chart_html = fig.to_html(full_html=False, include_plotlyjs='cdn')

    # Build the HTML table from the detailed activities
    table_rows = ""
    for act in activities:
        dt_object = pd.to_datetime(act['timestamp'])
        formatted_timestamp = dt_object.strftime('%d-%m-%Y %H:%M:%S')

        ticket_link = f"<a href='https://rndjira.sas.com/browse/{act['ticket']}' target='_blank'>{act['ticket']}</a>"
        table_rows += f"""
        <tr>
            <td>{formatted_timestamp}</td>
            <td>{act['type']}</td>
            <td>{ticket_link}</td>
            <td>{act['summary']}</td>
            <td>{act['author']}</td>
            <td>{act['message']}</td>
        </tr>
        """

    # Assemble the final HTML file
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Daily Push Report</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; background-color: #f8f9fa; }}
            .container {{ padding: 20px; max-width: 1200px; margin: auto; }}
            h1 {{ color: #333; }}
            h2 {{ color: #555; }}
            .subtitle {{ color: #666; font-size: 0.9em; margin-top: -15px; margin-bottom: 20px;}}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; background-color: #fff; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #007bff; color: white; }}
            tr:nth-child(even) {{ background-color: #f2f2f2; }}
            tr:hover {{ background-color: #ddd; }}
            a {{ color: #007bff; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Daily Push Report</h1>
            {chart_html}
            
            <h2>Detailed Activity</h2>
            <p class="subtitle">Data last refreshed on: {refresh_time}</p>
            <table>
                <thead>
                    <tr>
                        <th>Timestamp</th>
                        <th>Activity Type</th>
                        <th>Ticket</th>
                        <th>Summary</th>
                        <th>Author</th>
                        <th>Message/Title</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """

    # Write the timestamped HTML content to a file
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    logger.success(f"Generated timestamped HTML report at: {report_path}")

    # Save a copy with a consistent name for embedding
    latest_report_path = os.path.join(report_dir, 'latest_push_report.html')
    with open(latest_report_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    logger.success(f"Updated latest report at: {latest_report_path}")

    # Copy the latest report to the homepage directory
    homepage_dir = os.getenv('HOMEPAGE_REPORTS_DIR')
    if homepage_dir:
        try:
            os.makedirs(homepage_dir, exist_ok=True)
            destination_path = os.path.join(homepage_dir, 'latest_push_report.html')
            shutil.copy(latest_report_path, destination_path)
            logger.success(f"Copied latest report to homepage directory: {destination_path}")
        except Exception as e:
            logger.error(f"Failed to copy report to homepage directory: {e}")


def get_daily_push_report(jira):
    """
    Finds all tickets with commits or merged pull requests in the last N days
    and generates a report.
    """
    projects = os.getenv('JIRA_PROJECTS', '')
    if not projects:
        logger.error("JIRA_PROJECTS environment variable is not set")
        return

    days_to_check = os.getenv('JIRA_PUSH_REPORT_DAYS', '7')
    report_dir = os.getenv('JIRA_REPORT_DIR', './reports')
    os.makedirs(report_dir, exist_ok=True)

    jql_query = f"project in ({projects}) AND type in (Story, Bug) AND updated >= -{days_to_check}d AND (Development[pullrequests].status IS NOT EMPTY)"

    logger.searching("Running JQL query to find tickets with recent development activity")
    logger.debug(f"Query: {jql_query}")

    try:
        issues = jira.search_issues(jql_query, maxResults=1000)
        
        if not issues:
            logger.complete(f"No tickets with PR activity found in the last {days_to_check} days")
            return

        logger.info(f"Found {len(issues)} tickets with PR activity")
        
        activities = []
        time_window = datetime.now(datetime.now().astimezone().tzinfo) - timedelta(days=int(days_to_check))

        for issue in issues:
            dev_summary_string = issue.raw['fields'].get('customfield_13100')
            if not dev_summary_string:
                continue

            match = re.search(r"devSummaryJson=(.*)", dev_summary_string)
            if not match:
                continue
            
            json_substring = match.group(1)
            dev_summary_json = _extract_json_from_string(json_substring)

            if not dev_summary_json:
                logger.debug(f"Could not parse development summary for {issue.key}")
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
                        logger.debug(f"Found recent merged PR activity for {issue.key}")
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
                logger.debug(f"Could not process parsed summary for {issue.key}: {e}")

        if not activities:
            logger.complete(f"No recent merged PR activity found within the last {days_to_check} days")
            return

        # Generate the HTML report
        today_str = datetime.now().strftime('%Y-%m-%d')
        report_path = os.path.join(report_dir, f"daily_push_report_{today_str}.html")
        
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        
        generate_html_report(activities, report_path, days_to_check, report_dir)
        logger.complete("Daily push report generation completed successfully")

    except Exception as e:
        logger.exception(f"An error occurred while generating the report: {e}")


def main():
    """Main function to execute the daily push report."""
    log_section_header(logger, "DAILY PUSH REPORT")
    
    jira_client = connect_to_jira()
    if jira_client:
        get_daily_push_report(jira_client)


if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(dotenv_path=os.path.join(project_root, '.env'))
    
    from logging_config import setup_logging
    setup_logging()
    
    main()