# jira_automation/changelog_dashboard.py
"""
Changelog activity dashboard generation.

This module generates an interactive HTML dashboard with Plotly charts showing
Jira issue modification patterns: daily volume, per-issue frequency, day-of-week
trends, issue type breakdown, and employee activity heatmap.
"""

import os
import json
from datetime import datetime
from collections import defaultdict
from logging_utils import get_logger, log_section_header
from jira_data_analysis import db_utils

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data queries
# ---------------------------------------------------------------------------

def fetch_changelog_data(db_pool):
    """
    Fetches all changelog data from the database.

    Returns:
        List of dicts with keys: change_date, issue_key, project_key,
        issue_type, author_name, author_email, day_of_week, field_name
    """
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT change_date, issue_key, project_key, issue_type,
                       author_name, author_email, day_of_week, field_name
                FROM tbl_issue_changelog
                WHERE change_date IS NOT NULL
                ORDER BY change_date
            """)
            columns = ['change_date', 'issue_key', 'project_key', 'issue_type',
                        'author_name', 'author_email', 'day_of_week', 'field_name']
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
            logger.info(f"Fetched {len(rows)} changelog records from database")
            return rows
    except Exception as e:
        logger.error(f"Failed to fetch changelog data: {e}")
        return []
    finally:
        db_pool.putconn(conn)


def fetch_ldap_lookup(db_pool):
    """
    Builds a lookup dict from email -> display_name using LDAP data.

    Returns:
        Dict mapping lowercase email to display name
    """
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT LOWER(email), display_name FROM tbl_ldap_hierarchy WHERE email IS NOT NULL")
            lookup = {row[0]: row[1] for row in cur.fetchall()}
            logger.info(f"Loaded {len(lookup)} LDAP display name mappings")
            return lookup
    except Exception as e:
        logger.warning(f"Could not load LDAP data (heatmap will use Jira names): {e}")
        return {}
    finally:
        db_pool.putconn(conn)


# ---------------------------------------------------------------------------
# Chart data preparation
# ---------------------------------------------------------------------------

def prepare_chart_data(rows, ldap_lookup):
    """
    Pre-processes raw rows into JSON-serializable structures for all charts.

    Returns a dict with keys:
        dates, daily_counts, issue_type_dates, issue_type_series,
        dow_labels, dow_averages, per_issue_counts,
        heatmap_employees, heatmap_dow, heatmap_z,
        all_issue_types
    """
    if not rows:
        return None

    # --- Daily change volume (Chart 1) ---
    daily = defaultdict(int)
    # --- Issue type breakdown (Chart 4) ---
    type_daily = defaultdict(lambda: defaultdict(int))
    # --- Day-of-week (Chart 3) ---
    dow_totals = defaultdict(int)
    dow_date_sets = defaultdict(set)
    # --- Per-issue frequency (Chart 2) ---
    issue_date_counts = defaultdict(lambda: defaultdict(int))
    # --- Employee heatmap (Chart 5) ---
    employee_dow = defaultdict(lambda: defaultdict(int))

    all_issue_types = set()

    for r in rows:
        d = str(r['change_date'])
        itype = r['issue_type'] or 'Unknown'
        dow = r['day_of_week']
        issue_key = r['issue_key']

        # Resolve employee name: LDAP display_name > author_name > email
        email = r['author_email'] or ''
        name = ldap_lookup.get(email) or r['author_name'] or email or 'Unknown'

        daily[d] += 1
        type_daily[itype][d] += 1
        all_issue_types.add(itype)

        if dow is not None:
            dow_totals[dow] += 1
            dow_date_sets[dow].add(d)

        issue_date_counts[issue_key][d] += 1
        employee_dow[name][dow if dow is not None else 0] += 1

    # Sort dates
    dates = sorted(daily.keys())
    daily_counts = [daily[d] for d in dates]

    # Issue type series (sorted by total volume desc)
    sorted_types = sorted(all_issue_types, key=lambda t: sum(type_daily[t].values()), reverse=True)
    issue_type_series = {}
    for itype in sorted_types:
        issue_type_series[itype] = [type_daily[itype].get(d, 0) for d in dates]

    # Day-of-week averages
    dow_labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    dow_averages = []
    for i in range(7):
        num_days = len(dow_date_sets[i]) if dow_date_sets[i] else 1
        dow_averages.append(round(dow_totals[i] / num_days, 1))

    # Per-issue update frequency (histogram data)
    per_issue_counts = []
    for issue_key, date_counts in issue_date_counts.items():
        for d, count in date_counts.items():
            per_issue_counts.append(count)

    # Employee heatmap (top 30 by total activity)
    employee_totals = {name: sum(dows.values()) for name, dows in employee_dow.items()}
    sorted_employees = sorted(employee_totals.keys(), key=lambda n: employee_totals[n], reverse=True)

    top_n = 30
    top_employees = sorted_employees[:top_n]

    # Collapse remaining into "Other"
    if len(sorted_employees) > top_n:
        other_dow = defaultdict(int)
        for name in sorted_employees[top_n:]:
            for dow_idx, cnt in employee_dow[name].items():
                other_dow[dow_idx] += cnt
        employee_dow['Other'] = dict(other_dow)
        top_employees.append('Other')

    # Build heatmap z-matrix (employees x 7 days)
    heatmap_z = []
    for name in top_employees:
        row = [employee_dow[name].get(i, 0) for i in range(7)]
        heatmap_z.append(row)

    return {
        'dates': dates,
        'daily_counts': daily_counts,
        'issue_type_series': issue_type_series,
        'dow_labels': dow_labels,
        'dow_averages': dow_averages,
        'per_issue_counts': per_issue_counts,
        'heatmap_employees': top_employees,
        'heatmap_z': heatmap_z,
        'all_issue_types': sorted_types,
    }


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def generate_dashboard_html(chart_data):
    """
    Generates a complete HTML dashboard with 5 Plotly charts in tabs,
    plus a global issue-type multi-select filter.

    Args:
        chart_data: Dict from prepare_chart_data()

    Returns:
        Complete HTML string
    """
    timestamp = datetime.now().strftime('%d-%m-%Y %H:%M:%S')

    # Serialize data for client-side JS
    data_json = json.dumps(chart_data)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Changelog Activity Dashboard</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
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

        .filter-bar {{
            background-color: #fff;
            padding: 16px 30px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            display: flex;
            align-items: center;
            gap: 16px;
            flex-wrap: wrap;
        }}

        .filter-bar label {{
            font-weight: 600;
            color: #333;
            font-size: 14px;
            white-space: nowrap;
        }}

        .filter-bar select {{
            padding: 8px 12px;
            border: 1px solid #ccc;
            border-radius: 4px;
            font-size: 14px;
            min-width: 300px;
            max-width: 500px;
            font-family: inherit;
        }}

        .filter-bar select option {{
            padding: 4px;
        }}

        .tab-nav {{
            display: flex;
            gap: 0;
            margin-bottom: 20px;
            background-color: #fff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }}

        .tab-btn {{
            flex: 1;
            padding: 14px 24px;
            border: none;
            background-color: #fff;
            color: #666;
            font-size: 15px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
            border-bottom: 3px solid transparent;
            font-family: inherit;
        }}

        .tab-btn:hover {{
            background-color: #f5f5f5;
            color: #333;
        }}

        .tab-btn.active {{
            color: #1976d2;
            border-bottom-color: #1976d2;
            font-weight: 600;
        }}

        .tab-content {{
            display: none;
        }}

        .tab-content.active {{
            display: block;
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
            min-height: 450px;
        }}

        @media (max-width: 768px) {{
            body {{
                padding: 10px;
            }}
            .dashboard-header h1 {{
                font-size: 22px;
            }}
            .filter-bar {{
                flex-direction: column;
                align-items: flex-start;
            }}
            .filter-bar select {{
                min-width: 100%;
            }}
        }}
    </style>
</head>
<body>

<div class="dashboard-header">
    <h1>Changelog Activity Dashboard</h1>
    <p>Jira issue modification patterns &bull; Generated {timestamp}</p>
</div>

<div class="filter-bar">
    <label for="issueTypeFilter">Issue Types:</label>
    <select id="issueTypeFilter" multiple size="4">
    </select>
    <button onclick="resetFilter()" style="padding:8px 16px; border:1px solid #ccc; border-radius:4px; background:#fff; cursor:pointer; font-family:inherit; font-size:14px;">Reset</button>
</div>

<div class="tab-nav">
    <button class="tab-btn active" onclick="switchTab('daily-volume')">Daily Volume</button>
    <button class="tab-btn" onclick="switchTab('per-issue')">Per-Issue Frequency</button>
    <button class="tab-btn" onclick="switchTab('day-of-week')">Day of Week</button>
    <button class="tab-btn" onclick="switchTab('issue-types')">Issue Types</button>
    <button class="tab-btn" onclick="switchTab('heatmap')">Employee Heatmap</button>
</div>

<div id="tab-daily-volume" class="tab-content active">
    <div class="chart-container">
        <div class="chart-title">Daily Change Volume</div>
        <div id="chart-daily" class="chart-content"></div>
    </div>
</div>

<div id="tab-per-issue" class="tab-content">
    <div class="chart-container">
        <div class="chart-title">Per-Issue Update Frequency</div>
        <div id="chart-histogram" class="chart-content"></div>
    </div>
</div>

<div id="tab-day-of-week" class="tab-content">
    <div class="chart-container">
        <div class="chart-title">Average Changes by Day of Week</div>
        <div id="chart-dow" class="chart-content"></div>
    </div>
</div>

<div id="tab-issue-types" class="tab-content">
    <div class="chart-container">
        <div class="chart-title">Issue Type Breakdown (Stacked Area)</div>
        <div id="chart-types" class="chart-content"></div>
    </div>
</div>

<div id="tab-heatmap" class="tab-content">
    <div class="chart-container">
        <div class="chart-title">Employee Activity Heatmap</div>
        <div id="chart-heatmap" class="chart-content"></div>
    </div>
</div>

<script>
// ---------------------------------------------------------------------------
// Embedded data
// ---------------------------------------------------------------------------
var DATA = {data_json};

// ---------------------------------------------------------------------------
// Issue type filter
// ---------------------------------------------------------------------------
var allTypes = DATA.all_issue_types || [];
var selectedTypes = new Set(allTypes);

(function populateFilter() {{
    var sel = document.getElementById('issueTypeFilter');
    allTypes.forEach(function(t) {{
        var opt = document.createElement('option');
        opt.value = t;
        opt.textContent = t;
        opt.selected = true;
        sel.appendChild(opt);
    }});
    sel.addEventListener('change', function() {{
        selectedTypes = new Set();
        for (var i = 0; i < sel.options.length; i++) {{
            if (sel.options[i].selected) selectedTypes.add(sel.options[i].value);
        }}
        renderAll();
    }});
}})();

function resetFilter() {{
    var sel = document.getElementById('issueTypeFilter');
    for (var i = 0; i < sel.options.length; i++) sel.options[i].selected = true;
    selectedTypes = new Set(allTypes);
    renderAll();
}}

// ---------------------------------------------------------------------------
// Tab switching
// ---------------------------------------------------------------------------
function switchTab(tabId) {{
    document.querySelectorAll('.tab-content').forEach(function(el) {{
        el.classList.remove('active');
    }});
    document.querySelectorAll('.tab-btn').forEach(function(btn) {{
        btn.classList.remove('active');
    }});
    document.getElementById('tab-' + tabId).classList.add('active');
    // Find the button that matches
    document.querySelectorAll('.tab-btn').forEach(function(btn) {{
        if (btn.getAttribute('onclick').indexOf(tabId) !== -1) btn.classList.add('active');
    }});
    // Trigger Plotly resize on the active tab's chart
    var activeDiv = document.querySelector('#tab-' + tabId + ' .chart-content');
    if (activeDiv) Plotly.Plots.resize(activeDiv);
}}

// ---------------------------------------------------------------------------
// Chart rendering
// ---------------------------------------------------------------------------
var plotlyLayout = {{
    paper_bgcolor: 'white',
    plot_bgcolor: 'white',
    font: {{ family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" }},
    margin: {{ l: 60, r: 30, t: 40, b: 60 }},
    hovermode: 'x unified'
}};

var plotlyConfig = {{ displayModeBar: false, responsive: true }};

function filterByType(issueTypeSeries, dates) {{
    // Return per-date totals considering only selected issue types
    var totals = new Array(dates.length).fill(0);
    Object.keys(issueTypeSeries).forEach(function(t) {{
        if (selectedTypes.has(t)) {{
            issueTypeSeries[t].forEach(function(v, i) {{ totals[i] += v; }});
        }}
    }});
    return totals;
}}

function renderDaily() {{
    var filtered = filterByType(DATA.issue_type_series, DATA.dates);
    Plotly.react('chart-daily', [{{
        x: DATA.dates,
        y: filtered,
        type: 'bar',
        marker: {{ color: '#1976d2' }},
        hovertemplate: '%{{x}}<br>%{{y}} changes<extra></extra>'
    }}], Object.assign({{}}, plotlyLayout, {{
        xaxis: {{ title: 'Date', gridcolor: '#e0e0e0' }},
        yaxis: {{ title: 'Changelog Entries', gridcolor: '#e0e0e0' }}
    }}), plotlyConfig);
}}

function renderHistogram() {{
    // Per-issue counts are not filterable by type in the pre-computed data,
    // so we show the full distribution regardless of filter.
    Plotly.react('chart-histogram', [{{
        x: DATA.per_issue_counts,
        type: 'histogram',
        marker: {{ color: '#1976d2' }},
        hovertemplate: '%{{x}} changes/issue/day<br>Count: %{{y}}<extra></extra>'
    }}], Object.assign({{}}, plotlyLayout, {{
        xaxis: {{ title: 'Changes per Issue per Day', gridcolor: '#e0e0e0' }},
        yaxis: {{ title: 'Frequency', gridcolor: '#e0e0e0' }},
        bargap: 0.05
    }}), plotlyConfig);
}}

function renderDow() {{
    // Day-of-week not filterable by type (aggregate)
    Plotly.react('chart-dow', [{{
        x: DATA.dow_labels,
        y: DATA.dow_averages,
        type: 'bar',
        marker: {{ color: '#1976d2' }},
        hovertemplate: '%{{x}}<br>Avg: %{{y}} changes<extra></extra>'
    }}], Object.assign({{}}, plotlyLayout, {{
        xaxis: {{ title: 'Day of Week' }},
        yaxis: {{ title: 'Average Changes per Day', gridcolor: '#e0e0e0' }}
    }}), plotlyConfig);
}}

function renderTypes() {{
    var traces = [];
    var colors = [
        '#1976d2', '#c62828', '#2e7d32', '#f57c00', '#6a1b9a',
        '#00838f', '#ad1457', '#4e342e', '#37474f', '#558b2f'
    ];
    var idx = 0;
    Object.keys(DATA.issue_type_series).forEach(function(t) {{
        if (!selectedTypes.has(t)) return;
        traces.push({{
            x: DATA.dates,
            y: DATA.issue_type_series[t],
            name: t,
            type: 'scatter',
            mode: 'lines',
            stackgroup: 'one',
            line: {{ color: colors[idx % colors.length], width: 0 }},
            fillcolor: colors[idx % colors.length] + 'B3',
            hovertemplate: t + ': %{{y}}<extra></extra>'
        }});
        idx++;
    }});
    Plotly.react('chart-types', traces, Object.assign({{}}, plotlyLayout, {{
        xaxis: {{ title: 'Date', gridcolor: '#e0e0e0' }},
        yaxis: {{ title: 'Changelog Entries', gridcolor: '#e0e0e0' }},
        legend: {{ orientation: 'h', y: -0.2 }}
    }}), plotlyConfig);
}}

function renderHeatmap() {{
    Plotly.react('chart-heatmap', [{{
        x: DATA.dow_labels,
        y: DATA.heatmap_employees,
        z: DATA.heatmap_z,
        type: 'heatmap',
        colorscale: 'Blues',
        hovertemplate: '%{{y}}<br>%{{x}}: %{{z}} changes<extra></extra>'
    }}], Object.assign({{}}, plotlyLayout, {{
        margin: {{ l: 200, r: 30, t: 40, b: 60 }},
        yaxis: {{ autorange: 'reversed', tickfont: {{ size: 12 }} }},
        height: Math.max(450, DATA.heatmap_employees.length * 28 + 100)
    }}), plotlyConfig);
}}

function renderAll() {{
    renderDaily();
    renderHistogram();
    renderDow();
    renderTypes();
    renderHeatmap();
}}

// Initial render
renderAll();
</script>

</body>
</html>'''

    return html


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Generates the changelog activity dashboard HTML."""
    log_section_header(logger, "CHANGELOG DASHBOARD")

    logger.start("Starting changelog dashboard generation")

    db_pool = db_utils.get_connection_pool()

    rows = fetch_changelog_data(db_pool)
    if not rows:
        logger.warning("No changelog data found. Dashboard not generated.")
        return

    ldap_lookup = fetch_ldap_lookup(db_pool)
    chart_data = prepare_chart_data(rows, ldap_lookup)

    if not chart_data:
        logger.warning("Could not prepare chart data. Dashboard not generated.")
        return

    html = generate_dashboard_html(chart_data)

    report_dir = os.getenv('JIRA_REPORT_DIR', './reports')
    os.makedirs(report_dir, exist_ok=True)
    output_path = os.path.join(report_dir, 'changelog_dashboard.html')

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    logger.success(f"Changelog dashboard generated: {output_path}")
    logger.complete("Changelog dashboard generation completed successfully")


if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dotenv_path = os.path.join(project_root, '.env')
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=dotenv_path)

    from logging_config import setup_logging
    setup_logging()

    main()
