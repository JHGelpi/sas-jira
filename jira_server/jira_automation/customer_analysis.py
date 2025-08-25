import os
import json
from jira import JIRA
from dotenv import load_dotenv
import logging
from datetime import datetime
import csv
import shutil

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

def get_custom_field_id(jira, field_name: str) -> str | None:
    """Dynamically finds the custom field ID for a given field name."""
    try:
        all_fields = jira.fields()
        for field in all_fields:
            if field['name'].lower() == field_name.lower():
                logger.info(f"Found custom field ID for '{field_name}': {field['id']}")
                return field['id']
    except Exception as e:
        logger.error(f"Failed to retrieve custom fields: {e}")
    
    logger.error(f"Could not find a custom field named '{field_name}'.")
    return None

def generate_html_report(report_data: list, report_path: str):
    """Generates a self-contained HTML report with a data table."""
    logger.info("Generating HTML report for customer bugs...")
    
    refresh_time = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
    
    # Build the HTML table from the detailed activities
    table_rows = ""
    for row in report_data:
        ticket_link = f"<a href='{row['Issue URL']}' target='_blank'>{row['Issue Key']}</a>"
        table_rows += f"""
        <tr>
            <td>{ticket_link}</td>
            <td>{row['Created Date']}</td>
            <td>{row['Updated Date']}</td>
            <td>{row['Assignee']}</td>
            <td>{row['Origin']}</td>
            <td>{row['Priority']}</td>
        </tr>
        """

    # Assemble the final HTML file
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Open Customer Bugs Report</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; background-color: #f8f9fa; }}
            .container {{ padding: 20px; max-width: 1200px; margin: auto; }}
            h1 {{ color: #333; }}
            .subtitle {{ color: #666; font-size: 0.9em; margin-top: -15px; margin-bottom: 20px;}}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; background-color: #fff; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #d9534f; color: white; }}
            tr:nth-child(even) {{ background-color: #f2f2f2; }}
            tr:hover {{ background-color: #ddd; }}
            a {{ color: #007bff; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Open Customer Bugs Report</h1>
            <p class="subtitle">Data last refreshed on: {refresh_time}</p>
            <table>
                <thead>
                    <tr>
                        <th>Issue Key</th>
                        <th>Created Date</th>
                        <th>Updated Date</th>
                        <th>Assignee</th>
                        <th>Origin</th>
                        <th>Priority</th>
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

    # Write the HTML content to a file
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    logger.info(f"✅ Successfully generated HTML report at: {report_path}")

    # --- NEW: Copy the report to the homepage directory ---
    homepage_dir = os.getenv('HOMEPAGE_REPORTS_DIR')
    if homepage_dir:
        try:
            # Ensure the destination directory exists and copy the file
            os.makedirs(homepage_dir, exist_ok=True)
            destination_path = os.path.join(homepage_dir, 'customer_bugs_report.html')
            shutil.copy(report_path, destination_path)
            logger.info(f"✅ Successfully copied report to homepage directory: {destination_path}")
        except Exception as e:
            logger.error(f"❌ Failed to copy report to homepage directory: {e}")


def analyze_customer_bugs(jira):
    """
    Finds open bugs with customer labels, updates the Origin field if needed,
    and generates an HTML report.
    """
    # 1. Load the customer data from the JSON file
    json_path = os.getenv('JIRA_CUSTOMER_JSON_PATH', 'helper_files/customer_support_lvls.json')
    try:
        with open(json_path, 'r') as f:
            customer_data = json.load(f)
    except FileNotFoundError:
        logger.error(f"❌ Customer JSON file not found at '{json_path}'. Aborting.")
        return
    except json.JSONDecodeError:
        logger.error(f"❌ Could not parse JSON from '{json_path}'. Aborting.")
        return

    # 2. Collect all unique labels from the JSON file
    all_customer_labels = set()
    for customer in customer_data:
        labels = customer.get("jira_label", [])
        if isinstance(labels, list):
            all_customer_labels.update(labels)
    
    if not all_customer_labels:
        logger.warning("No Jira labels found in the customer JSON file. Exiting.")
        return

    # 3. Get the custom field ID for "Origin"
    origin_field_id = get_custom_field_id(jira, "Origin")
    if not origin_field_id:
        logger.error("❌ Could not find the 'Origin' custom field. Aborting.")
        return

    # 4. Construct and run the JQL query
    projects = os.getenv('JIRA_PROJECTS', '')
    labels_jql = ", ".join([f'"{label}"' for label in all_customer_labels])
    jql_query = (
        f"project in ({projects}) AND type = Bug AND statusCategory != Done AND "
        f"labels in ({labels_jql})"
    )

    logger.info("🔍 Running JQL query to find open customer bugs...")
    logger.info(f"   Query: {jql_query}")

    try:
        fields_to_fetch = ["summary", "assignee", "created", "updated", "priority", origin_field_id]
        issues = jira.search_issues(jql_query, fields=fields_to_fetch, maxResults=False)

        if not issues:
            logger.info("🎉 No open bugs found with customer labels.")
            # Still generate an empty report
            report_data = []
        else:
            logger.info(f"Found {len(issues)} open customer bugs. Processing...")
            report_data = []
            for issue in issues:
                # Action #2: Update the Origin field if it is empty
                origin_value = getattr(issue.fields, origin_field_id, None)
                if not origin_value:
                    logger.info(f"  -> Updating Origin for {issue.key} to 'CRP PLAT'...")
                    try:
                        issue.update(fields={origin_field_id: {'value': 'CRP PLAT'}})
                        logger.info(f"✅ Successfully updated {issue.key}.")
                        origin_value_str = "CRP PLAT" 
                    except Exception as e:
                        logger.error(f"❌ Failed to update {issue.key}: {e}")
                        origin_value_str = "Update Failed"
                else:
                    origin_value_str = origin_value.value if hasattr(origin_value, 'value') else str(origin_value)

                # Prepare data for the report
                assignee = issue.fields.assignee.displayName if issue.fields.assignee else "Unassigned"
                priority = issue.fields.priority.name if issue.fields.priority else "N/A"
                
                report_data.append({
                    "Issue Key": issue.key,
                    "Issue URL": f"https://rndjira.sas.com/browse/{issue.key}",
                    "Created Date": issue.fields.created,
                    "Updated Date": issue.fields.updated,
                    "Assignee": assignee,
                    "Origin": origin_value_str,
                    "Priority": priority
                })

        # Action #1: Write all found bugs to an HTML file
        report_dir = os.getenv('JIRA_REPORT_DIR', './reports')
        os.makedirs(report_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y-%m-%d')
        report_path = os.path.join(report_dir, f"customer_open_bugs_{timestamp}.html")
        
        generate_html_report(report_data, report_path)

    except Exception as e:
        logger.error(f"❌ An error occurred during the customer analysis process: {e}")

def main():
    """Main function to execute the customer analysis."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(dotenv_path=os.path.join(project_root, '.env'))
    
    jira_client = connect_to_jira()
    if jira_client:
        analyze_customer_bugs(jira_client)

if __name__ == "__main__":
    main()
