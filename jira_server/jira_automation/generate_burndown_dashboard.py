# jira_automation/generate_burndown_dashboard.py
"""
Burndown dashboard generation.

This module generates a tabbed HTML dashboard that organizes COMPDIV burndown
charts into two tabs:
- Overview: All COMPDIV*.html files in a 3-column grid
- BIGINT: All COMPLANG*.html and COMPHOST*.html files in a 3-column grid

Files are sorted alphabetically (A->Z) on each tab.
"""

import os
import re
from pathlib import Path
from typing import List, Tuple
from datetime import datetime
from logging_utils import get_logger, log_section_header
from jira_data_analysis import db_utils

logger = get_logger(__name__)


def get_epic_status_from_db(epic_key: str, db_pool) -> Tuple[bool, str]:
    """
    Fetch epic status from tbl_initiative_issue_keys.

    *** READ-ONLY FUNCTION - NEVER MODIFIES DATA ***

    Args:
        epic_key: The epic key to look up (e.g., "COMPDIV-123")
        db_pool: Database connection pool

    Returns:
        Tuple of (is_active, eff_end_date_str)
        - is_active: True if active_flag is NULL/True, False if active_flag is False
        - eff_end_date_str: Date string (YYYY-MM-DD) or empty string if not closed
    """
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT active_flag, eff_end_date
                FROM tbl_initiative_issue_keys
                WHERE issue_key = %s
                """,
                (epic_key,)
            )
            row = cur.fetchone()
            if row:
                active_flag, eff_end_date = row
                # Consider NULL or True as active, False as closed
                is_active = active_flag is None or active_flag is True
                eff_end_date_str = eff_end_date.strftime('%Y-%m-%d') if eff_end_date and not is_active else ''
                return is_active, eff_end_date_str
    except Exception as e:
        logger.debug(f"Could not fetch status for {epic_key}: {e}")
    finally:
        db_pool.putconn(conn)

    # Default: assume active if not found in database
    return True, ''


def collect_html_files(burndown_dir: str) -> Tuple[List[str], List[str], List[str]]:
    """
    Scans the burndown directory and collects HTML files for each tab.

    Returns:
        Tuple of (overview_files, bigint_files, iris_files) - all lists sorted alphabetically
    """
    overview_files = []
    bigint_files = []
    iris_files = []

    try:
        files = [f for f in os.listdir(burndown_dir) if f.endswith('_burndown.html')]
        logger.info(f"Found {len(files)} burndown HTML files")

        for filename in files:
            # IRIS files have IRIS_ prefix and go exclusively to IRIS tab
            if filename.startswith('IRIS_'):
                iris_files.append(filename)
            elif filename.startswith('COMPDIV'):
                overview_files.append(filename)
            elif filename.startswith('COMPLANG') or filename.startswith('COMPHOST'):
                bigint_files.append(filename)
            else:
                # Any other files go to Overview by default
                overview_files.append(filename)

        # Sort alphabetically
        overview_files.sort()
        bigint_files.sort()
        iris_files.sort()

        logger.info(f"Overview tab: {len(overview_files)} files")
        logger.info(f"BIGINT tab: {len(bigint_files)} files")
        logger.info(f"IRIS tab: {len(iris_files)} files")

    except Exception as e:
        logger.error(f"Failed to collect HTML files: {e}")

    return overview_files, bigint_files, iris_files


def extract_epic_title(html_path: str) -> Tuple[str, str]:
    """
    Extracts the epic title and key from the HTML file by reading the Plotly title.
    Falls back to the filename if extraction fails.

    Returns:
        Tuple of (title, epic_key) where epic_key is None if not found
    """
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Look for the title in the Plotly layout
            # Pattern: "title":{"text":"Epic Title (COMPDIV-123)...
            # Use a pattern that handles escaped quotes: (?:[^"\\]|\\.)*
            # This matches either: non-quote/non-backslash OR backslash followed by any character
            match = re.search(r'"title"\s*:\s*\{\s*"text"\s*:\s*"((?:[^"\\]|\\.)*)"', content)
            if match:
                title = match.group(1)

                # Decode unicode escapes (e.g., \u003c -> <, \" -> ")
                title = title.encode().decode('unicode_escape')

                # Remove everything starting from <br> (including the HTML tags)
                # This handles both cases: titles with/without closing parenthesis before <br>
                title = re.split(r'<br>', title)[0]

                title = title.strip()

                # Extract epic key from title (e.g., "COMPDIV-120" from "Epic Title (COMPDIV-120)")
                epic_key_match = re.search(r'\(([A-Z]+-\d+)\)', title)
                epic_key = epic_key_match.group(1) if epic_key_match else None

                return title, epic_key
    except Exception as e:
        logger.debug(f"Could not extract title from {html_path}: {e}")

    # Fallback: use filename without extension
    fallback_title = Path(html_path).stem.replace('_burndown', '')
    # Try to extract epic key from filename
    epic_key_match = re.search(r'([A-Z]+-\d+)', fallback_title)
    epic_key = epic_key_match.group(1) if epic_key_match else None
    return fallback_title, epic_key


def generate_dashboard_html(burndown_dir: str, output_path: str) -> None:
    """
    Generates the dashboard HTML file with tabs for Overview, BIGINT, and IRIS.

    Args:
        burndown_dir: Directory containing the burndown HTML files
        output_path: Path where the dashboard HTML should be written
    """
    log_section_header(logger, "BURNDOWN DASHBOARD GENERATION")
    logger.start("Starting burndown dashboard generation")

    overview_files, bigint_files, iris_files = collect_html_files(burndown_dir)

    if not overview_files and not bigint_files and not iris_files:
        logger.warning("No burndown HTML files found. Dashboard not generated.")
        return

    logger.processing("Building dashboard HTML structure")

    # Initialize database connection pool for status lookups (READ-ONLY)
    db_pool = db_utils.get_connection_pool()

    # Read the HTML content for each file and extract titles + status
    overview_charts = []
    for filename in overview_files:
        filepath = os.path.join(burndown_dir, filename)
        title, epic_key = extract_epic_title(filepath)

        # Fetch epic status from database (READ-ONLY)
        is_active, eff_end_date = True, ''
        if epic_key:
            is_active, eff_end_date = get_epic_status_from_db(epic_key, db_pool)

        overview_charts.append({
            'filename': filename,
            'title': title,
            'epic_key': epic_key,
            'is_active': is_active,
            'eff_end_date': eff_end_date,
            'path': filepath
        })

    bigint_charts = []
    for filename in bigint_files:
        filepath = os.path.join(burndown_dir, filename)
        title, epic_key = extract_epic_title(filepath)

        # Fetch epic status from database (READ-ONLY)
        is_active, eff_end_date = True, ''
        if epic_key:
            is_active, eff_end_date = get_epic_status_from_db(epic_key, db_pool)

        bigint_charts.append({
            'filename': filename,
            'title': title,
            'epic_key': epic_key,
            'is_active': is_active,
            'eff_end_date': eff_end_date,
            'path': filepath
        })

    iris_charts = []
    for filename in iris_files:
        filepath = os.path.join(burndown_dir, filename)
        title, epic_key = extract_epic_title(filepath)

        # Fetch epic status from database (READ-ONLY)
        is_active, eff_end_date = True, ''
        if epic_key:
            is_active, eff_end_date = get_epic_status_from_db(epic_key, db_pool)

        iris_charts.append({
            'filename': filename,
            'title': title,
            'epic_key': epic_key,
            'is_active': is_active,
            'eff_end_date': eff_end_date,
            'path': filepath
        })

    # Two-tier sorting: Active epics first, then alphabetically by epic_key
    # Sort key: (not is_active, epic_key) - False (active) sorts before True (closed)
    overview_charts.sort(key=lambda x: (not x.get('is_active', True), x.get('epic_key', '')))
    bigint_charts.sort(key=lambda x: (not x.get('is_active', True), x.get('epic_key', '')))
    iris_charts.sort(key=lambda x: (not x.get('is_active', True), x.get('epic_key', '')))

    logger.info(f"Sorted charts: Active epics at top, closed at bottom, alphabetical within each group")

    # Generate the HTML
    html_content = generate_html_structure(overview_charts, bigint_charts, iris_charts, burndown_dir)

    # Write the dashboard file
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.success(f"Dashboard generated successfully: {output_path}")
    except Exception as e:
        logger.error(f"Failed to write dashboard HTML: {e}")
        raise


def generate_html_structure(overview_charts: List[dict], bigint_charts: List[dict], iris_charts: List[dict], burndown_dir: str) -> str:
    """
    Generates the complete HTML structure for the dashboard.

    Args:
        overview_charts: List of chart metadata for Overview tab
        bigint_charts: List of chart metadata for BIGINT tab
        iris_charts: List of chart metadata for IRIS tab
        burndown_dir: Base directory for burndown files (for relative paths)

    Returns:
        Complete HTML string
    """

    def generate_grid_html(charts: List[dict]) -> str:
        """Generate the 3-column grid HTML for a list of charts."""
        if not charts:
            return '<p style="text-align: center; padding: 40px; color: #666;">No charts available</p>'

        grid_html = '<div class="chart-grid">\n'
        for chart in charts:
            # Create clickable title if epic_key exists
            if chart.get('epic_key'):
                jira_url = f"https://rndjira.sas.com/browse/{chart['epic_key']}"
                is_active = chart.get('is_active', True)
                title_class = "epic-link"

                # Add completed epic styling if inactive
                if not is_active:
                    title_class += " completed-epic"
                    eff_end_date = chart.get('eff_end_date', 'Unknown')
                    title_html = f'<a href="{jira_url}" target="_blank" class="{title_class}">{chart["title"]} <span class="completed-badge">[COMPLETED: {eff_end_date}]</span></a>'
                else:
                    title_html = f'<a href="{jira_url}" target="_blank" class="{title_class}">{chart["title"]}</a>'
            else:
                title_html = chart['title']

            grid_html += f'''
    <div class="chart-card">
        <div class="chart-title">{title_html}</div>
        <iframe src="{chart['filename']}" class="chart-iframe"></iframe>
        <div class="chart-link">
            <a href="{chart['filename']}" target="_blank">Open in new tab ↗</a>
        </div>
    </div>
'''
        grid_html += '</div>\n'
        return grid_html

    overview_html = generate_grid_html(overview_charts)
    bigint_html = generate_grid_html(bigint_charts)
    iris_html = generate_grid_html(iris_charts)

    # Generate timestamp in dd-mm-yyyy HH:MM:SS format
    timestamp = datetime.now().strftime('%d-%m-%Y %H:%M:%S')

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>COMPDIV Burndown Dashboard</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background-color: #f5f5f5;
            padding: 20px;
        }}

        .dashboard-header {{
            background-color: #fff;
            padding: 20px 30px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}

        .dashboard-header h1 {{
            color: #333;
            font-size: 28px;
            margin-bottom: 8px;
        }}

        .dashboard-header p {{
            color: #666;
            font-size: 14px;
        }}

        .tabs {{
            background-color: #fff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }}

        .tab-buttons {{
            display: flex;
            border-bottom: 2px solid #e0e0e0;
            background-color: #fafafa;
        }}

        .tab-button {{
            flex: 1;
            padding: 16px 24px;
            background: none;
            border: none;
            cursor: pointer;
            font-size: 16px;
            font-weight: 500;
            color: #666;
            transition: all 0.3s ease;
            position: relative;
        }}

        .tab-button:hover {{
            background-color: #f0f0f0;
            color: #333;
        }}

        .tab-button.active {{
            color: #1976d2;
            background-color: #fff;
        }}

        .tab-button.active::after {{
            content: '';
            position: absolute;
            bottom: -2px;
            left: 0;
            right: 0;
            height: 3px;
            background-color: #1976d2;
        }}

        .tab-count {{
            display: inline-block;
            margin-left: 8px;
            padding: 2px 8px;
            background-color: #e3f2fd;
            color: #1976d2;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }}

        .tab-button.active .tab-count {{
            background-color: #1976d2;
            color: #fff;
        }}

        .tab-content {{
            display: none;
            padding: 30px;
        }}

        .tab-content.active {{
            display: block;
        }}

        .chart-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 24px;
            max-width: 100%;
        }}

        @media (max-width: 1600px) {{
            .chart-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}

        @media (max-width: 1000px) {{
            .chart-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        .chart-card {{
            background-color: #fff;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            min-width: 450px;
        }}

        .chart-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 4px 16px rgba(0,0,0,0.15);
        }}

        .chart-title {{
            padding: 16px 20px;
            background-color: #f8f9fa;
            border-bottom: 1px solid #e0e0e0;
            font-weight: 600;
            color: #333;
            font-size: 14px;
        }}

        .chart-title .epic-link {{
            color: #333;
            text-decoration: none;
            transition: color 0.2s ease;
        }}

        .chart-title .epic-link:hover {{
            color: #1976d2;
            text-decoration: underline;
        }}

        .chart-title .epic-link.completed-epic {{
            color: #c62828;  /* Bold red for completed epics */
            font-weight: 700;
        }}

        .chart-title .epic-link.completed-epic:hover {{
            color: #b71c1c;  /* Darker red on hover */
        }}

        .completed-badge {{
            display: inline-block;
            font-size: 11px;
            font-weight: 700;
            color: #c62828;
            margin-left: 8px;
            padding: 2px 6px;
            background-color: #ffebee;
            border-radius: 3px;
            border: 1px solid #ef9a9a;
        }}

        .chart-iframe {{
            width: 100%;
            height: 500px;
            border: none;
            display: block;
        }}

        .chart-link {{
            padding: 12px 20px;
            background-color: #fafafa;
            border-top: 1px solid #e0e0e0;
            text-align: right;
        }}

        .chart-link a {{
            color: #1976d2;
            text-decoration: none;
            font-size: 13px;
            font-weight: 500;
        }}

        .chart-link a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="dashboard-header">
        <h1>COMPDIV Burndown Dashboard</h1>
        <p>Epic burndown charts organized by team - Updated: {timestamp}</p>
    </div>

    <div class="tabs">
        <div class="tab-buttons">
            <button class="tab-button active" onclick="switchTab(event, 'overview')">
                Overview
                <span class="tab-count">{len(overview_charts)}</span>
            </button>
            <button class="tab-button" onclick="switchTab(event, 'bigint')">
                BIGINT
                <span class="tab-count">{len(bigint_charts)}</span>
            </button>
            <button class="tab-button" onclick="switchTab(event, 'iris')">
                IRIS
                <span class="tab-count">{len(iris_charts)}</span>
            </button>
            <button class="tab-button" onclick="switchTab(event, 'bugtrends')">
                Bug Trends
            </button>
        </div>

        <div id="overview" class="tab-content active">
            {overview_html}
        </div>

        <div id="bigint" class="tab-content">
            {bigint_html}
        </div>

        <div id="iris" class="tab-content">
            {iris_html}
        </div>

        <div id="bugtrends" class="tab-content">
            <iframe src="bug_trends_report.html" style="width: 100%; height: calc(100vh - 200px); border: none;"></iframe>
        </div>
    </div>

    <script>
        // Track if tabs have been initialized
        const tabsInitialized = {{}};

        function switchTab(event, tabId) {{
            // Hide all tab contents
            const tabContents = document.querySelectorAll('.tab-content');
            tabContents.forEach(content => {{
                content.classList.remove('active');
            }});

            // Remove active class from all buttons
            const tabButtons = document.querySelectorAll('.tab-button');
            tabButtons.forEach(button => {{
                button.classList.remove('active');
            }});

            // Show selected tab content
            const selectedTab = document.getElementById(tabId);
            selectedTab.classList.add('active');

            // Add active class to clicked button
            event.currentTarget.classList.add('active');

            // Force iframes to reload on first view to fix legend truncation
            // This only happens once per tab to avoid unnecessary reloads
            if (!tabsInitialized[tabId]) {{
                setTimeout(() => {{
                    const iframes = selectedTab.querySelectorAll('iframe');
                    iframes.forEach(iframe => {{
                        // Force iframe to reload by resetting its src
                        const src = iframe.src;
                        iframe.src = '';
                        setTimeout(() => {{
                            iframe.src = src;
                        }}, 10);
                    }});
                    tabsInitialized[tabId] = true;
                }}, 100);
            }}
        }}
    </script>
</body>
</html>
'''

    return html


def main():
    """Main entry point for dashboard generation."""
    burndown_dir = os.getenv('COMPDIV_BURNDOWN_DIR')
    if not burndown_dir:
        logger.error("COMPDIV_BURNDOWN_DIR environment variable not set")
        return

    if not os.path.exists(burndown_dir):
        logger.error(f"Burndown directory does not exist: {burndown_dir}")
        return

    # Generate dashboard in the same directory
    output_path = os.path.join(burndown_dir, 'dashboard.html')

    generate_dashboard_html(burndown_dir, output_path)

    logger.complete("Dashboard generation completed successfully")


if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dotenv_path = os.path.join(project_root, '.env')
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=dotenv_path)

    from logging_config import setup_logging
    setup_logging()

    main()
