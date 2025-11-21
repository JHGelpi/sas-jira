# jira_automation/generate_bug_charts.py
"""
Bug trend chart generation.

This module generates HTML reports with Plotly charts showing bug trends
over time from the collected snapshot data.
"""

import os
import pandas as pd
import plotly.express as px
from datetime import date, timedelta
from sqlalchemy import create_engine, text
import shutil
from logging_utils import get_logger, log_section_header

logger = get_logger(__name__)


def generate_bug_trends_html(fig1, fig2, bug_details_by_release=None):
    """
    Generates HTML content for the bug trends report matching the dashboard.html theme.

    Args:
        fig1: Plotly figure for Outstanding Open Bugs chart
        fig2: Plotly figure for Bugs by Release chart
        bug_details_by_release: Dictionary mapping release versions to lists of bug details

    Returns:
        Complete HTML string with consistent styling
    """
    from datetime import datetime
    import json

    timestamp = datetime.now().strftime('%d-%m-%Y %H:%M:%S')

    # Generate Plotly HTML for charts
    chart1_html = fig1.to_html(full_html=False, include_plotlyjs='cdn', div_id='bug-trends-chart1') if fig1 else '<p style="text-align: center; padding: 40px; color: #666;">No data available for Outstanding Open Bugs chart</p>'
    chart2_html = fig2.to_html(full_html=False, include_plotlyjs='cdn', div_id='bug-trends-chart2') if fig2 else '<p style="text-align: center; padding: 40px; color: #666;">No data available for Bugs by Release chart</p>'

    # Convert bug details to JSON for JavaScript
    bug_details_json = json.dumps(bug_details_by_release or {})

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bug Trends Report</title>
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

        .chart-container {{
            background-color: #fff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 30px;
            margin-bottom: 20px;
        }}

        .chart-title {{
            font-weight: 600;
            color: #333;
            font-size: 18px;
            margin-bottom: 20px;
        }}

        .chart-content {{
            width: 100%;
            min-height: 500px;
        }}

        .bug-details-table-container {{
            background-color: #fff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 30px;
            margin-top: 20px;
            display: none;
        }}

        .bug-details-table-container.visible {{
            display: block;
        }}

        .table-header {{
            font-weight: 600;
            color: #333;
            font-size: 16px;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #1976d2;
        }}

        .bug-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}

        .bug-table thead {{
            background-color: #f8f9fa;
            border-bottom: 2px solid #e0e0e0;
        }}

        .bug-table th {{
            padding: 12px 16px;
            text-align: left;
            font-weight: 600;
            color: #333;
        }}

        .bug-table tbody tr {{
            border-bottom: 1px solid #e0e0e0;
            transition: background-color 0.2s ease;
        }}

        .bug-table tbody tr:hover {{
            background-color: #f5f5f5;
        }}

        .bug-table td {{
            padding: 12px 16px;
        }}

        .bug-link {{
            color: #1976d2;
            text-decoration: none;
            font-weight: 500;
        }}

        .bug-link:hover {{
            text-decoration: underline;
        }}

        .no-bugs-message {{
            text-align: center;
            padding: 40px;
            color: #666;
            font-style: italic;
        }}
    </style>
</head>
<body>
    <div class="dashboard-header">
        <h1>Bug Trends Report</h1>
        <p>Bug trend analysis from snapshot data - Updated: {timestamp}</p>
    </div>

    <div class="chart-container">
        <div class="chart-title">Daily Open Bugs (Last 6 Months)</div>
        <div class="chart-content">
            {chart1_html}
        </div>
    </div>

    <div class="chart-container">
        <div class="chart-title">Bugs by Release (Current Snapshot)</div>
        <div class="chart-content">
            {chart2_html}
        </div>
    </div>

    <div id="bug-details-table-container" class="bug-details-table-container">
        <div class="table-header" id="table-header"></div>
        <div id="table-content"></div>
    </div>

    <script>
        // Bug details data embedded from backend
        const bugDetailsByRelease = {bug_details_json};

        // Add click event handler to the Bugs by Release chart
        const chart2Element = document.getElementById('bug-trends-chart2');

        if (chart2Element) {{
            chart2Element.on('plotly_click', function(data) {{
                // Get the clicked bar's information
                const point = data.points[0];
                const release = point.x;
                const state = point.data.name;  // "Open" or "Closed"

                // Only show table for "Open" bugs
                if (state !== 'Open') {{
                    hideTable();
                    return;
                }}

                // Get bug details for this release
                const bugs = bugDetailsByRelease[release];

                if (!bugs || bugs.length === 0) {{
                    showEmptyTable(release);
                    return;
                }}

                // Show the table with bug details
                showBugTable(release, bugs);
            }});
        }}

        function showBugTable(release, bugs) {{
            const container = document.getElementById('bug-details-table-container');
            const header = document.getElementById('table-header');
            const content = document.getElementById('table-content');

            // Set header
            header.textContent = `Open Bugs for Release: ${{release}} (${{bugs.length}} bug${{bugs.length !== 1 ? 's' : ''}})`;

            // Build table HTML
            let tableHtml = `
                <table class="bug-table">
                    <thead>
                        <tr>
                            <th>Issue ID</th>
                            <th>Summary</th>
                            <th>Last Modified</th>
                        </tr>
                    </thead>
                    <tbody>
            `;

            bugs.forEach(bug => {{
                const jiraUrl = `https://rndjira.sas.com/browse/${{bug.issue_key}}`;
                tableHtml += `
                    <tr>
                        <td><a href="${{jiraUrl}}" target="_blank" class="bug-link">${{bug.issue_key}}</a></td>
                        <td>${{bug.summary || 'N/A'}}</td>
                        <td>${{bug.updated_str || 'N/A'}}</td>
                    </tr>
                `;
            }});

            tableHtml += `
                    </tbody>
                </table>
            `;

            content.innerHTML = tableHtml;
            container.classList.add('visible');

            // Scroll to table
            container.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
        }}

        function showEmptyTable(release) {{
            const container = document.getElementById('bug-details-table-container');
            const header = document.getElementById('table-header');
            const content = document.getElementById('table-content');

            header.textContent = `Open Bugs for Release: ${{release}}`;
            content.innerHTML = '<div class="no-bugs-message">No open bugs found for this release.</div>';

            container.classList.add('visible');
        }}

        function hideTable() {{
            const container = document.getElementById('bug-details-table-container');
            container.classList.remove('visible');
        }}
    </script>
</body>
</html>
'''
    return html


def main():
    """Generates the bug trend charts from the snapshot data."""
    log_section_header(logger, "BUG TREND CHART GENERATION")
    
    logger.start("Starting bug chart generation")
    
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        logger.error("DATABASE_URL is not set")
        return

    try:
        engine = create_engine(db_url)
        conn = engine.connect()
        logger.success("Connected to database")
    except Exception as e:
        logger.error(f"Failed to create database engine: {e}")
        return

    try:
        logger.searching("Fetching all bug snapshot data from the last 6 months")
        six_months_ago = date.today() - timedelta(days=180)
        sql = text("""
            SELECT snapshot_date, issue_key, issue_type, status_category, origin,
                   affects_version, fix_version, assignee, pipeline_discovery_stage,
                   project_key, summary, updated
            FROM tbl_bug_snapshots
            WHERE issue_type = 'Bug' AND snapshot_date >= :start_date
        """)
        df = pd.read_sql(sql, conn, params={'start_date': six_months_ago})
        logger.info(f"Fetched {len(df)} total bug snapshot records")

    except Exception as e:
        logger.error(f"Failed to fetch data from database: {e}")
        return
    finally:
        conn.close()
        
    if df.empty:
        logger.warning("No data found to generate charts")
        return

    # Define a modern color palette
    color_palette = {
        'COMPDIV': '#1f77b4', 'COMPTRIAGE': '#ff7f0e', 'COMPLANG': '#2ca02c',
        'COMPUTESVCS': '#d62728', 'COMPWLM': '#9467bd', 'COMPHOST': '#8c564b',
        'COMPBEIJING': '#e377c2', 'GEMINI': '#7f7f7f', 'COMPSRVCORE': '#bcbd22',
        'COMPCONNECT': '#17becf', 'COMPOBSERVE': '#aec7e8', 'COMPDIVPUNE': '#ffbb78',
        'COMPSRVCAS': '#98df8a'
    }

    # Chart 1: Outstanding Open Bugs (Line Chart with CRP Filter)
    logger.processing("Generating Outstanding Open Bugs chart")

    # Filter to only open bugs (not Done)
    df_open = df[df['status_category'] != 'Done'].copy()

    # Mark which bugs are CRP
    df_open['is_crp'] = df_open['origin'].str.contains('CRP', na=False)

    fig1 = None
    if not df_open.empty:
        import plotly.graph_objects as go

        # Prepare data for ALL bugs (default view)
        daily_counts_all = df_open.groupby(['snapshot_date', 'project_key']).size().reset_index(name='open_bugs')
        total_daily_all = df_open.groupby('snapshot_date').size().reset_index(name='total_bugs')

        # Prepare data for CRP bugs only
        df_crp = df_open[df_open['is_crp']]
        daily_counts_crp = df_crp.groupby(['snapshot_date', 'project_key']).size().reset_index(name='open_bugs')
        total_daily_crp = df_crp.groupby('snapshot_date').size().reset_index(name='total_bugs')

        # Get complete list of all projects that appear in either dataset
        all_projects = sorted(set(daily_counts_all['project_key'].unique()) | set(daily_counts_crp['project_key'].unique()))

        # Create figure
        fig1 = go.Figure()

        # Track trace indices for visibility toggling
        trace_indices = []

        # Add traces for each project (ALL bugs first, then CRP bugs)
        for project in all_projects:
            color = color_palette.get(project, None)

            # Get data for this project
            project_data_all = daily_counts_all[daily_counts_all['project_key'] == project]
            project_data_crp = daily_counts_crp[daily_counts_crp['project_key'] == project]

            # Trace for ALL bugs (visible by default)
            fig1.add_trace(go.Scatter(
                x=project_data_all['snapshot_date'] if not project_data_all.empty else [],
                y=project_data_all['open_bugs'] if not project_data_all.empty else [],
                mode='lines+markers',
                name=project,
                line=dict(color=color),
                marker=dict(symbol='circle'),
                visible=True,
                legendgroup=project,
                showlegend=True
            ))

            # Trace for CRP bugs only (hidden by default)
            fig1.add_trace(go.Scatter(
                x=project_data_crp['snapshot_date'] if not project_data_crp.empty else [],
                y=project_data_crp['open_bugs'] if not project_data_crp.empty else [],
                mode='lines+markers',
                name=project,
                line=dict(color=color),
                marker=dict(symbol='circle'),
                visible=False,
                legendgroup=project,
                showlegend=True
            ))

        # Add aggregate total line for ALL bugs
        fig1.add_trace(go.Scatter(
            x=total_daily_all['snapshot_date'],
            y=total_daily_all['total_bugs'],
            mode='lines+markers',
            name='Total (All Projects)',
            line=dict(color='black', width=3, dash='dash'),
            marker=dict(size=6, color='black'),
            visible=True
        ))

        # Add aggregate total line for CRP bugs only
        fig1.add_trace(go.Scatter(
            x=total_daily_crp['snapshot_date'],
            y=total_daily_crp['total_bugs'],
            mode='lines+markers',
            name='Total (All Projects)',
            line=dict(color='black', width=3, dash='dash'),
            marker=dict(size=6, color='black'),
            visible=False
        ))

        # Create visibility arrays for dropdown
        num_projects = len(all_projects)
        # Each project has 2 traces (ALL and CRP), plus 2 total traces at the end
        # For "All Bugs": show first trace of each project + first total
        visible_all = []
        for i in range(num_projects):
            visible_all.extend([True, False])  # Show ALL, hide CRP
        visible_all.extend([True, False])  # Show ALL total, hide CRP total

        # For "CRP Only": show second trace of each project + second total
        visible_crp = []
        for i in range(num_projects):
            visible_crp.extend([False, True])  # Hide ALL, show CRP
        visible_crp.extend([False, True])  # Hide ALL total, show CRP total

        # Add dropdown menu
        fig1.update_layout(
            updatemenus=[
                dict(
                    buttons=list([
                        dict(
                            args=[{"visible": visible_all}],
                            label="All Bugs",
                            method="update"
                        ),
                        dict(
                            args=[{"visible": visible_crp}],
                            label="CRP Only",
                            method="update"
                        )
                    ]),
                    direction="down",
                    pad={"r": 10, "t": 10},
                    showactive=True,
                    x=1.02,
                    xanchor="left",
                    y=1.08,
                    yanchor="bottom",
                    bgcolor="white",
                    bordercolor="gray",
                    borderwidth=1
                )
            ],
            xaxis=dict(title='Date', type='date'),
            yaxis=dict(title='Number of Open Bugs'),
            title='Daily Open Bugs (Last 6 Months)',
            hovermode='x unified',
            legend=dict(title='Project')
        )

        logger.success("Generated Outstanding Open Bugs chart with CRP filter")
    else:
        logger.warning("No data found for the 'Outstanding Open Bugs' chart")

    # Chart 2: Bugs by Release (Grouped with Project Hover Info)
    logger.processing("Generating Bugs by Release chart")
    df_latest = df[df['snapshot_date'] == df['snapshot_date'].max()].copy()

    fig2 = None
    bug_details_by_release = {}  # Dictionary to store bug details for each release
    if not df_latest.empty:
        df_latest['is_crp'] = df_latest['origin'].str.contains('CRP', na=False)
        df_latest['state'] = df_latest['status_category'].apply(lambda x: 'Open' if x != 'Done' else 'Closed')
        df_latest['release'] = df_latest['affects_version'].str.split(',').str[0].str.strip()

        # Prepare detailed bug data for open bugs by release
        df_open_bugs = df_latest[df_latest['state'] == 'Open'].copy()
        # Convert updated timestamp to string for JSON serialization
        df_open_bugs['updated_str'] = pd.to_datetime(df_open_bugs['updated']).dt.strftime('%Y-%m-%d %H:%M:%S')

        for release in df_open_bugs['release'].dropna().unique():
            release_bugs = df_open_bugs[df_open_bugs['release'] == release]
            bug_details_by_release[release] = release_bugs[['issue_key', 'summary', 'updated_str']].to_dict('records')

        bugs_by_release_detailed = df_latest.groupby(['release', 'project_key', 'is_crp', 'state']).size().reset_index(name='count')

        hover_text_df = bugs_by_release_detailed.groupby(['release', 'state']).apply(
            lambda g: '<br>'.join([f"{row.project_key}: {row['count']}" for _, row in g.iterrows()])
        ).reset_index(name='project_breakdown')

        bugs_by_release_agg = bugs_by_release_detailed.groupby(['release', 'state'])['count'].sum().reset_index()
        chart_df = pd.merge(bugs_by_release_agg, hover_text_df, on=['release', 'state'])

        fig2 = px.bar(chart_df, x='release', y='count', color='state',
                      title='Bugs by Release (Current Snapshot)',
                      labels={'release': 'Release Version', 'count': 'Number of Bugs', 'state': 'Status'},
                      category_orders={'release': sorted(chart_df['release'].dropna().unique())},
                      barmode='group',
                      custom_data=['project_breakdown'])

        fig2.update_traces(
            hovertemplate="<b>Release:</b> %{x}<br><b>Status:</b> %{data.name}<br><b>Total Bugs:</b> %{y}<br><b>Project Breakdown:</b><br>%{customdata[0]}<extra></extra>"
        )
        logger.success("Generated Bugs by Release chart")
    else:
        logger.warning("No data found for the 'Bugs by Release' chart")

    # Generate HTML (matching dashboard.html theme)
    report_dir = os.getenv('JIRA_REPORT_DIR', './reports')
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, "bug_trends_report.html")

    logger.processing("Generating HTML report with dashboard theme")
    try:
        with open(report_path, 'w') as f:
            f.write(generate_bug_trends_html(fig1, fig2, bug_details_by_release))
        logger.success(f"Successfully generated bug trends report at {report_path}")
    except Exception as e:
        logger.error(f"Failed to write HTML report: {e}")
        return

    # Copy to homepage directory
    homepage_dir = os.getenv('HOMEPAGE_REPORTS_DIR')
    if homepage_dir:
        try:
            shutil.copy(report_path, homepage_dir)
            logger.success(f"Copied report to {homepage_dir}")
        except Exception as e:
            logger.error(f"Failed to copy report to homepage directory: {e}")

    # Copy to burndown directory for dashboard integration
    burndown_dir = os.getenv('COMPDIV_BURNDOWN_DIR')
    if burndown_dir:
        try:
            os.makedirs(burndown_dir, exist_ok=True)
            burndown_report_path = os.path.join(burndown_dir, "bug_trends_report.html")
            shutil.copy(report_path, burndown_report_path)
            logger.success(f"Copied report to burndown directory: {burndown_report_path}")
        except Exception as e:
            logger.error(f"Failed to copy report to burndown directory: {e}")
    
    logger.complete("Bug chart generation completed successfully")


if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dotenv_path = os.path.join(project_root, '.env')
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=dotenv_path)
    
    from logging_config import setup_logging
    setup_logging()
    
    main()