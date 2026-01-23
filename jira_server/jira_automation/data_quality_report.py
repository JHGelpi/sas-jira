# jira_automation/data_quality_report.py
"""
Data quality reporting and enforcement.

This module runs multiple JQL queries to find tickets with missing or incorrect data,
generates consolidated reports, and sends granular notifications by manager.
"""

import os
import re
import csv
from datetime import datetime
from collections import defaultdict
from jira import JIRA
from jira_data_analysis import db_utils
from jira_automation import notification_utils
from dotenv import load_dotenv
from logging_utils import get_logger, log_section_header, log_subsection_header

logger = get_logger(__name__)

# Field names to look up
FIELD_NAMES_TO_FIND = {
    "origin": "Origin",
    "pipeline_discovery": "Pipeline Discovery Stage",
    "platform_version": "Platform Version",
    "severity": "Severity",
}


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


def get_custom_field_ids(jira) -> dict:
    """Dynamically finds the custom field IDs for a given set of field names."""
    logger.info("Fetching custom field IDs from Jira")
    custom_field_ids = {}
    try:
        all_fields = jira.fields()
        field_map = {field['name'].lower(): field['id'] for field in all_fields}
        
        for key, name in FIELD_NAMES_TO_FIND.items():
            field_id = field_map.get(name.lower())
            if field_id:
                custom_field_ids[key] = field_id
                logger.debug(f"Found ID for '{name}': {field_id}")
            else:
                logger.warning(f"Could not find custom field named '{name}'")
    except Exception as e:
        logger.error(f"Failed to retrieve custom fields: {e}")
    
    return custom_field_ids


def get_ldap_data_from_db(db_pool) -> dict:
    """
    Fetches user data from the LDAP hierarchy table and returns a dictionary
    mapping employee emails to their manager info.
    """
    logger.database("Fetching LDAP hierarchy data from PostgreSQL")
    ldap_map = {}
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT email, manager_name, manager_email FROM tbl_ldap_hierarchy")
            for row in cursor.fetchall():
                if row[0]:
                    ldap_map[row[0].lower()] = {
                        'manager_name': row[1],
                        'manager_email': row[2]
                    }
        logger.info(f"Loaded {len(ldap_map)} user records for manager lookup")
    except Exception as e:
        logger.error(f"Failed to fetch LDAP data from database: {e}")
    finally:
        db_pool.putconn(conn)
    return ldap_map


def get_project_exclusion_clause() -> str:
    """
    Builds a JQL clause to exclude projects from data quality reporting.

    Reads from DATA_QUALITY_EXCLUDE_PROJECTS environment variable which should
    contain a comma-separated list of project keys (e.g., "SIGNOFF,TESTPROJ").

    Returns:
        JQL clause like "AND project NOT IN (SIGNOFF, TESTPROJ)" or empty string if no exclusions
    """
    excluded_projects = os.getenv('DATA_QUALITY_EXCLUDE_PROJECTS', '').strip()
    if not excluded_projects:
        return ""

    # Split by comma and clean up whitespace
    project_keys = [p.strip() for p in excluded_projects.split(',') if p.strip()]

    if not project_keys:
        return ""

    # Build JQL clause
    projects_str = ', '.join(project_keys)
    logger.debug(f"Excluding projects from data quality report: {projects_str}")
    return f"AND project NOT IN ({projects_str})"


def fetch_issues_for_report(jira, jql_env_var: str, report_name: str, reason: str,
                            custom_field_ids: dict, ldap_map: dict) -> list:
    """Runs a JQL query and returns a list of processed issue data, enriched with manager info."""
    jql_query = os.getenv(jql_env_var)
    if not jql_query:
        logger.skip(f"Environment variable '{jql_env_var}' not set")
        return []

    # Add project exclusion clause before ORDER BY if present
    project_exclusion = get_project_exclusion_clause()
    if project_exclusion:
        # Find ORDER BY clause (case-insensitive) and insert exclusion before it
        order_by_match = re.search(r'\s+ORDER\s+BY\s+', jql_query, re.IGNORECASE)
        if order_by_match:
            # Insert exclusion before ORDER BY
            insert_pos = order_by_match.start()
            jql_query = jql_query[:insert_pos] + f" {project_exclusion} " + jql_query[insert_pos:]
        else:
            # No ORDER BY, append to end
            jql_query = f"{jql_query} {project_exclusion}"

    log_subsection_header(logger, report_name)
    logger.searching("Running query")
    logger.debug(f"Query: {jql_query}")

    processed_issues = []
    try:
        fields_to_fetch = [
            "summary", "assignee", "fixVersions", "versions",
            *custom_field_ids.values()
        ]
        fields_to_fetch = [f for f in fields_to_fetch if f]

        issues = jira.search_issues(jql_query, fields=fields_to_fetch, maxResults=500)

        if not issues:
            logger.info("No issues found matching the criteria")
            return []

        logger.info(f"Found {len(issues)} issues")
        
        for issue in issues:
            assignee = issue.fields.assignee.displayName if issue.fields.assignee else "Unassigned"
            assignee_email = issue.fields.assignee.emailAddress.lower() if issue.fields.assignee else None
            
            # Look up manager info from the pre-loaded map
            manager_info = ldap_map.get(assignee_email, {}) if assignee_email else {}
            manager_name = manager_info.get('manager_name')
            manager_email = manager_info.get('manager_email')

            fix_versions = ', '.join([v.name for v in issue.fields.fixVersions])
            affects_versions = ', '.join([v.name for v in issue.fields.versions])

            origin_id = custom_field_ids.get("origin")
            origin_val = getattr(issue.fields, origin_id, None) if origin_id else None

            pipeline_disc_id = custom_field_ids.get("pipeline_discovery")
            pipeline_disc_val = getattr(issue.fields, pipeline_disc_id, None) if pipeline_disc_id else None

            plat_ver_id = custom_field_ids.get("platform_version")
            plat_ver_val = getattr(issue.fields, plat_ver_id, None) if plat_ver_id else None

            severity_id = custom_field_ids.get("severity")
            severity_val = getattr(issue.fields, severity_id, None) if severity_id else None

            processed_issues.append({
                "Reason": reason,
                "Issue Key": issue.key,
                "Issue URL": f"https://rndjira.sas.com/browse/{issue.key}",
                "Assignee": assignee,
                "Assignee Email": assignee_email,
                "Assignee Manager": manager_name,
                "Assignee Manager Email": manager_email,
                "Fix Version": fix_versions,
                "Origin": origin_val.value if hasattr(origin_val, 'value') else origin_val,
                "Pipeline Discovery Stage": pipeline_disc_val.value if hasattr(pipeline_disc_val, 'value') else pipeline_disc_val,
                "Platform Version": plat_ver_val.value if hasattr(plat_ver_val, 'value') else plat_ver_val,
                "Severity": severity_val.value if hasattr(severity_val, 'value') else severity_val,
                "Affects Version": affects_versions
            })
            
    except Exception as e:
        logger.exception(f"An error occurred while fetching data for report '{report_name}': {e}")
    
    return processed_issues


def check_invalid_fix_versions_for_done_issues(jira, custom_field_ids: dict, ldap_map: dict) -> list:
    """
    Finds Done issues without valid fix versions using JQL query from environment.

    Uses the JQL_INVALID_FIXVER environment variable to find Done issues that have
    empty fix versions or only placeholder versions (Now, Next, Future).

    Args:
        jira: Jira client instance
        custom_field_ids: Dictionary of custom field IDs
        ldap_map: Dictionary mapping employee emails to manager info

    Returns:
        List of processed issue data for issues with invalid fix versions
    """
    return fetch_issues_for_report(
        jira,
        "JQL_INVALID_FIXVER",
        "Invalid Fix Versions for Done Issues",
        "Invalid Fix Version for Done Issue",
        custom_field_ids,
        ldap_map
    )


def write_consolidated_report(all_issues_data: list):
    """Writes the consolidated list of issues to a CSV and sends notifications by manager."""
    if not all_issues_data:
        logger.info("No issues found across all queries")
        return

    # CSV Generation
    report_dir = os.getenv('JIRA_REPORT_DIR', './reports')
    os.makedirs(report_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y-%m-%d')
    report_path = os.path.join(report_dir, f"data_quality_report_{timestamp}.csv")
    
    header = [
        "Reason", "Issue Key", "Issue URL", "Assignee", "Assignee Email",
        "Assignee Manager", "Assignee Manager Email", "Fix Version", "Origin",
        "Pipeline Discovery Stage", "Platform Version", "Severity", "Affects Version"
    ]
    
    try:
        logger.database(f"Writing consolidated report to {report_path}")
        with open(report_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            writer.writerows(all_issues_data)
        logger.success(f"Generated consolidated report: {report_path}")
    except Exception as e:
        logger.error(f"Failed to write consolidated CSV report: {e}")

    # Send granular Teams notifications by manager
    if os.getenv('TEAMS_WEBHOOK_URL_V2') or os.getenv('TEAMS_WEBHOOK_URL'):
        logger.processing("Preparing Teams notifications by manager")
        issues_by_manager = defaultdict(list)
        unmanaged_issues = []

        # First pass: group issues by assignee's manager (existing behavior)
        for row in all_issues_data:
            manager_name = row.get("Assignee Manager")
            if manager_name:
                issues_by_manager[manager_name].append(row)
            else:
                unmanaged_issues.append(row)

        # Build a mapping of manager email -> manager name from all issues
        manager_email_to_name = {}
        for row in all_issues_data:
            mgr_email = row.get("Assignee Manager Email")
            mgr_name = row.get("Assignee Manager")
            if mgr_email and mgr_name:
                manager_email_to_name[mgr_email.lower()] = mgr_name

        # Second pass: add tickets assigned directly to managers
        for row in all_issues_data:
            assignee_email = row.get("Assignee Email")
            if assignee_email:
                assignee_email_lower = assignee_email.lower()
                # Check if this assignee is a manager
                if assignee_email_lower in manager_email_to_name:
                    manager_name = manager_email_to_name[assignee_email_lower]
                    # Add this issue to the manager's own list (if not already there)
                    if row not in issues_by_manager[manager_name]:
                        issues_by_manager[manager_name].append(row)
                        logger.debug(f"Added self-assigned ticket {row['Issue Key']} to {manager_name}'s list")

        # Send a notification for each manager (with batching to avoid payload size limits)
        sent_count = 0
        BATCH_SIZE = 15  # Max issues per notification to stay under Power Automate size limits

        for manager_name, issues in sorted(issues_by_manager.items()):
            manager_email = issues[0].get("Assignee Manager Email")

            # Split issues into batches
            issue_batches = [issues[i:i + BATCH_SIZE] for i in range(0, len(issues), BATCH_SIZE)]

            for batch_num, issue_batch in enumerate(issue_batches, 1):
                batch_suffix = f" (Part {batch_num}/{len(issue_batches)})" if len(issue_batches) > 1 else ""
                title = f"Jira Data Quality Action Items for {manager_name}'s Team{batch_suffix}"
                mentions = [{'name': manager_name, 'email': manager_email}] if manager_email else []

                # Build the card body with a FactSet for each issue
                intro_text = f"Please review the following {len(issue_batch)} tickets assigned to you or your team that require data quality updates:"
                if len(issue_batches) > 1:
                    intro_text = f"Please review the following {len(issue_batch)} tickets (batch {batch_num} of {len(issue_batches)}, total {len(issues)} issues) assigned to you or your team that require data quality updates:"

                body_elements = [{
                    "type": "TextBlock",
                    "text": intro_text,
                    "wrap": True
                }]

                for issue in issue_batch:
                    issue_link = f"[{issue['Issue Key']}]({issue['Issue URL']})"
                    body_elements.append({
                        "type": "FactSet",
                        "facts": [
                            {"title": "Issue:", "value": issue_link},
                            {"title": "Assignee:", "value": issue.get('Assignee', 'Unassigned')},
                            {"title": "Reason:", "value": issue.get('Reason', 'N/A')},
                            {"title": "JQL:", "value": "JQL Confluence Page: https://rndconfluence.sas.com/x/Kul4L"}
                        ],
                        "separator": True
                    })

                notification_utils.send_teams_notification(title, body_elements, mentions)
                sent_count += 1

        logger.success(f"Sent {sent_count} Teams notifications to managers")

        # Send notification for unmanaged issues to fallback recipient (with batching)
        if unmanaged_issues:
            logger.warning(f"Found {len(unmanaged_issues)} issues with no manager information in LDAP")

            fallback_name = os.getenv('DATA_QUALITY_FALLBACK_NAME')
            fallback_email = os.getenv('DATA_QUALITY_FALLBACK_EMAIL')

            if fallback_name and fallback_email:
                logger.processing(f"Sending unmanaged issues notification to {fallback_name}")

                # Split unmanaged issues into batches
                unmanaged_batches = [unmanaged_issues[i:i + BATCH_SIZE] for i in range(0, len(unmanaged_issues), BATCH_SIZE)]

                for batch_num, issue_batch in enumerate(unmanaged_batches, 1):
                    batch_suffix = f" (Part {batch_num}/{len(unmanaged_batches)})" if len(unmanaged_batches) > 1 else ""
                    title = f"Jira Data Quality Action Items - Unassigned Manager{batch_suffix}"
                    mentions = [{'name': fallback_name, 'email': fallback_email}]

                    # Build the card body with a FactSet for each issue
                    intro_text = f"The following {len(issue_batch)} tickets have no manager information in LDAP and require data quality updates:"
                    if len(unmanaged_batches) > 1:
                        intro_text = f"The following {len(issue_batch)} tickets (batch {batch_num} of {len(unmanaged_batches)}, total {len(unmanaged_issues)} issues) have no manager information in LDAP and require data quality updates:"

                    body_elements = [{
                        "type": "TextBlock",
                        "text": intro_text,
                        "wrap": True
                    }]

                    for issue in issue_batch:
                        issue_link = f"[{issue['Issue Key']}]({issue['Issue URL']})"
                        body_elements.append({
                            "type": "FactSet",
                            "facts": [
                                {"title": "Issue:", "value": issue_link},
                                {"title": "Assignee:", "value": issue.get('Assignee', 'Unassigned')},
                                {"title": "Reason:", "value": issue.get('Reason', 'N/A')},
                                {"title": "JQL:", "value": "JQL Confluence Page: https://rndconfluence.sas.com/x/Kul4L"}
                            ],
                            "separator": True
                        })

                    notification_utils.send_teams_notification(title, body_elements, mentions)

                logger.success(f"Sent {len(unmanaged_batches)} notification(s) with {len(unmanaged_issues)} unmanaged issues")
            else:
                logger.warning("DATA_QUALITY_FALLBACK_NAME or DATA_QUALITY_FALLBACK_EMAIL not set. Cannot send unmanaged issues notification.")


def main():
    """Main function to execute all data quality reports."""
    log_section_header(logger, "DATA QUALITY REPORT")
    
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(dotenv_path=os.path.join(project_root, '.env'))
    
    jira_client = connect_to_jira()
    if not jira_client:
        return

    db_pool = db_utils.get_connection_pool()
    ldap_map = get_ldap_data_from_db(db_pool)
    custom_field_ids = get_custom_field_ids(jira_client)

    reports_to_run = {
        "JQL_MISSING_FIXVER": ("Missing Fix Version Report", "Missing Fix Version"),
        "JQL_MISSING_ORIGIN": ("Missing Origin Report", "Missing Origin"),
        "JQL_MISSING_PIPEDISC": ("Missing Pipeline Discovery Report", "Missing Pipeline Discovery Stage"),
        "JQL_MISSING_PLATVER": ("Missing Platform Version Report", "Missing Platform Version"),
        "JQL_MISSING_SEVERITY": ("Missing Severity Report", "Missing Severity"),
        "JQL_MISSING_AFFVER": ("Missing Affects Version Report", "Missing Affects Version")
    }

    all_issues_data = []
    for jql_var, (report_name, reason) in reports_to_run.items():
        issues_found = fetch_issues_for_report(jira_client, jql_var, report_name, reason, custom_field_ids, ldap_map)
        if issues_found:
            all_issues_data.extend(issues_found)

    # Check for invalid fix versions on Done issues
    logger.processing("Checking for Done issues with invalid fix versions")
    invalid_fix_version_issues = check_invalid_fix_versions_for_done_issues(jira_client, custom_field_ids, ldap_map)
    if invalid_fix_version_issues:
        all_issues_data.extend(invalid_fix_version_issues)

    write_consolidated_report(all_issues_data)
    logger.complete("Data quality report generation completed successfully")


if __name__ == "__main__":
    from logging_config import setup_logging
    setup_logging()
    main()