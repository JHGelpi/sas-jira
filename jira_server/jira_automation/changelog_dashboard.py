# jira_automation/changelog_dashboard.py
"""
Changelog activity dashboard generation.

This module generates an interactive HTML dashboard with Plotly charts showing
Jira issue modification patterns: daily volume, day-of-week trends, issue type
breakdown, and employee activity heatmap with week selection.

All data is scoped to a rolling 6-week window. The issue type filter applies
globally to every chart.
"""

import os
import json
from datetime import datetime, date, timedelta
from collections import defaultdict
from logging_utils import get_logger, log_section_header
from jira_data_analysis import db_utils

logger = get_logger(__name__)

ROLLING_WEEKS = 6


# ---------------------------------------------------------------------------
# Data queries
# ---------------------------------------------------------------------------

def fetch_changelog_data(db_pool):
    """
    Fetches changelog data from the last ROLLING_WEEKS weeks.

    Returns:
        List of dicts with keys: change_date, issue_key, project_key,
        issue_type, author_name, author_email, day_of_week, field_name
    """
    cutoff = date.today() - timedelta(weeks=ROLLING_WEEKS)
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT change_date, issue_key, project_key, issue_type,
                       author_name, author_email, day_of_week, field_name
                FROM tbl_issue_changelog
                WHERE change_date IS NOT NULL
                  AND change_date >= %s
                ORDER BY change_date
            """, (cutoff,))
            columns = ['change_date', 'issue_key', 'project_key', 'issue_type',
                        'author_name', 'author_email', 'day_of_week', 'field_name']
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
            logger.info(f"Fetched {len(rows)} changelog records (last {ROLLING_WEEKS} weeks, since {cutoff})")
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
# Data preparation
# ---------------------------------------------------------------------------

def prepare_chart_data(rows, ldap_lookup):
    """
    Converts raw DB rows into compact JSON-friendly structures.

    To support global issue-type filtering on every chart, we send per-row
    data encoded as parallel index arrays so the browser can re-aggregate
    on the fly.

    The employee list includes ALL LDAP employees so the heatmap can
    highlight those with zero activity.

    Returns a dict ready for json.dumps().
    """
    if not rows:
        return None

    # Build lookup indexes
    date_set = sorted({str(r['change_date']) for r in rows})
    date_idx = {d: i for i, d in enumerate(date_set)}

    type_set = sorted({r['issue_type'] or 'Unknown' for r in rows})
    type_idx = {t: i for i, t in enumerate(type_set)}

    # Employee list: ONLY people in the LDAP table (your direct/indirect reports)
    ldap_emails = set(ldap_lookup.keys())
    all_ldap_names = sorted(set(ldap_lookup.values()))
    emp_list = all_ldap_names

    emp_idx = {n: i for i, n in enumerate(emp_list)}

    # Resolve each row's author; mark non-LDAP authors as None (excluded)
    row_emp_indices = []
    for r in rows:
        email = (r['author_email'] or '').lower()
        if email in ldap_emails:
            name = ldap_lookup[email]
            row_emp_indices.append(emp_idx[name])
        else:
            row_emp_indices.append(-1)  # not in LDAP -- will be skipped

    # Build compact parallel arrays: [date_i, type_i, dow, emp_i]
    # Skip records from authors not in LDAP (emp_i == -1)
    records = []
    for i, r in enumerate(rows):
        e_i = row_emp_indices[i]
        if e_i == -1:
            continue
        d_i = date_idx[str(r['change_date'])]
        t_i = type_idx[r['issue_type'] or 'Unknown']
        dow = r['day_of_week'] if r['day_of_week'] is not None else 0
        records.append([d_i, t_i, dow, e_i])

    # Compute default date range: most recent completed Mon-Fri work week
    today = date.today()
    # Find the most recent Friday on or before today
    days_since_fri = (today.weekday() - 4) % 7  # weekday(): Mon=0..Sun=6, Fri=4
    if days_since_fri == 0 and today.weekday() == 4:
        # Today is Friday -- use this week
        default_to = today
    else:
        default_to = today - timedelta(days=days_since_fri)
    default_from = default_to - timedelta(days=4)  # Monday of that week

    logger.info(f"Prepared data: {len(records)} records, {len(date_set)} dates, "
                f"{len(type_set)} types, {len(emp_list)} employees")
    logger.info(f"Default heatmap range: {default_from} to {default_to}")

    return {
        'dates': date_set,
        'types': type_set,
        'employees': emp_list,
        'records': records,
        'defaultFrom': str(default_from),
        'defaultTo': str(default_to),
    }


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def generate_dashboard_html(chart_data):
    """
    Generates a complete HTML dashboard with 4 Plotly charts in tabs,
    a global issue-type multi-select filter, and a week slider for the heatmap.

    Args:
        chart_data: Dict from prepare_chart_data()

    Returns:
        Complete HTML string
    """
    timestamp = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
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

        .filter-btn {{
            padding: 8px 16px;
            border: 1px solid #ccc;
            border-radius: 4px;
            background: #fff;
            cursor: pointer;
            font-family: inherit;
            font-size: 14px;
        }}

        .filter-btn:hover {{
            background: #f5f5f5;
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

        .date-range-container {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 16px;
            flex-wrap: wrap;
        }}

        .date-range-container label {{
            font-weight: 600;
            color: #333;
            font-size: 14px;
            white-space: nowrap;
        }}

        .date-range-container input[type="date"] {{
            padding: 8px 12px;
            border: 1px solid #ccc;
            border-radius: 4px;
            font-size: 14px;
            font-family: inherit;
        }}

        .date-range-container .range-sep {{
            color: #666;
            font-size: 14px;
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
    <p>Jira issue modification patterns (rolling {ROLLING_WEEKS} weeks) &bull; Generated {timestamp}</p>
</div>

<div class="filter-bar">
    <label for="issueTypeFilter">Issue Types:</label>
    <select id="issueTypeFilter" multiple size="4">
    </select>
    <button class="filter-btn" onclick="resetFilter()">Reset</button>
</div>

<div class="tab-nav">
    <button class="tab-btn active" onclick="switchTab('daily-volume')">Daily Volume</button>
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
        <div class="date-range-container">
            <label for="dateFrom">Start:</label>
            <input type="date" id="dateFrom">
            <span class="range-sep">to</span>
            <label for="dateTo">End:</label>
            <input type="date" id="dateTo">
        </div>
        <div id="chart-heatmap" class="chart-content"></div>
    </div>
</div>

<script>
// ---------------------------------------------------------------------------
// Embedded data
// ---------------------------------------------------------------------------
var DATA = {data_json};
// records: [[date_i, type_i, dow, emp_i], ...]

var allTypes = DATA.types || [];
var selectedTypes = new Set(allTypes);

// ---------------------------------------------------------------------------
// Issue type filter (global)
// ---------------------------------------------------------------------------
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
// Date range setup (Start / End date pickers)
// ---------------------------------------------------------------------------
var heatmapFromDate = DATA.defaultFrom;
var heatmapToDate = DATA.defaultTo;

(function setupDateRange() {{
    var fromInput = document.getElementById('dateFrom');
    var toInput = document.getElementById('dateTo');

    // Set min/max to the data range
    var minDate = DATA.dates[0];
    var maxDate = DATA.dates[DATA.dates.length - 1];
    fromInput.min = minDate;
    fromInput.max = maxDate;
    toInput.min = minDate;
    toInput.max = maxDate;

    // Clamp defaults to available data range
    if (heatmapFromDate < minDate) heatmapFromDate = minDate;
    if (heatmapToDate > maxDate) heatmapToDate = maxDate;
    if (heatmapFromDate > heatmapToDate) heatmapFromDate = heatmapToDate;

    fromInput.value = heatmapFromDate;
    toInput.value = heatmapToDate;

    fromInput.addEventListener('change', function() {{
        heatmapFromDate = this.value;
        if (heatmapToDate < heatmapFromDate) {{
            heatmapToDate = heatmapFromDate;
            toInput.value = heatmapToDate;
        }}
        renderHeatmap();
    }});
    toInput.addEventListener('change', function() {{
        heatmapToDate = this.value;
        if (heatmapFromDate > heatmapToDate) {{
            heatmapFromDate = heatmapToDate;
            fromInput.value = heatmapFromDate;
        }}
        renderHeatmap();
    }});
}})();

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
    document.querySelectorAll('.tab-btn').forEach(function(btn) {{
        if (btn.getAttribute('onclick').indexOf(tabId) !== -1) btn.classList.add('active');
    }});
    var activeDiv = document.querySelector('#tab-' + tabId + ' .chart-content');
    if (activeDiv) Plotly.Plots.resize(activeDiv);
}}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function isSelected(rec) {{
    return selectedTypes.has(DATA.types[rec[1]]);
}}

var plotlyLayout = {{
    paper_bgcolor: 'white',
    plot_bgcolor: 'white',
    font: {{ family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" }},
    margin: {{ l: 60, r: 30, t: 40, b: 60 }},
    hovermode: 'x unified'
}};

var plotlyConfig = {{ displayModeBar: false, responsive: true }};

// ---------------------------------------------------------------------------
// Chart 1: Daily Change Volume
// ---------------------------------------------------------------------------
function renderDaily() {{
    var counts = new Array(DATA.dates.length).fill(0);
    DATA.records.forEach(function(rec) {{
        if (isSelected(rec)) counts[rec[0]] += 1;
    }});
    Plotly.react('chart-daily', [{{
        x: DATA.dates,
        y: counts,
        type: 'bar',
        marker: {{ color: '#1976d2' }},
        hovertemplate: '%{{x}}<br>%{{y}} changes<extra></extra>'
    }}], Object.assign({{}}, plotlyLayout, {{
        xaxis: {{ title: 'Date', gridcolor: '#e0e0e0' }},
        yaxis: {{ title: 'Changelog Entries', gridcolor: '#e0e0e0' }}
    }}), plotlyConfig);
}}

// ---------------------------------------------------------------------------
// Chart 2: Day of Week (average)
// ---------------------------------------------------------------------------
function renderDow() {{
    var dowLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    var dowTotals = [0,0,0,0,0,0,0];
    var dowDateSets = [new Set(), new Set(), new Set(), new Set(), new Set(), new Set(), new Set()];

    DATA.records.forEach(function(rec) {{
        if (!isSelected(rec)) return;
        var dow = rec[2];
        dowTotals[dow] += 1;
        dowDateSets[dow].add(rec[0]);  // date index as proxy for unique date
    }});

    var avgs = dowLabels.map(function(_, i) {{
        var numDays = dowDateSets[i].size || 1;
        return Math.round(dowTotals[i] / numDays * 10) / 10;
    }});

    Plotly.react('chart-dow', [{{
        x: dowLabels,
        y: avgs,
        type: 'bar',
        marker: {{ color: '#1976d2' }},
        hovertemplate: '%{{x}}<br>Avg: %{{y}} changes<extra></extra>'
    }}], Object.assign({{}}, plotlyLayout, {{
        xaxis: {{ title: 'Day of Week' }},
        yaxis: {{ title: 'Average Changes per Day', gridcolor: '#e0e0e0' }}
    }}), plotlyConfig);
}}

// ---------------------------------------------------------------------------
// Chart 3: Issue Type Breakdown (stacked area)
// ---------------------------------------------------------------------------
function renderTypes() {{
    // Build per-type per-date counts (only selected types)
    var typeCounts = {{}};
    allTypes.forEach(function(t) {{ typeCounts[t] = new Array(DATA.dates.length).fill(0); }});

    DATA.records.forEach(function(rec) {{
        var t = DATA.types[rec[1]];
        typeCounts[t][rec[0]] += 1;
    }});

    var colors = [
        '#1976d2', '#c62828', '#2e7d32', '#f57c00', '#6a1b9a',
        '#00838f', '#ad1457', '#4e342e', '#37474f', '#558b2f'
    ];
    var traces = [];
    var idx = 0;
    allTypes.forEach(function(t) {{
        if (!selectedTypes.has(t)) return;
        traces.push({{
            x: DATA.dates,
            y: typeCounts[t],
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

// ---------------------------------------------------------------------------
// Chart 4: Employee Activity Heatmap (date range filtered)
// ---------------------------------------------------------------------------
function renderHeatmap() {{
    var dowLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

    // Find which date indices fall in the selected date range
    var rangeDateIndices = new Set();
    DATA.dates.forEach(function(d, i) {{
        if (d >= heatmapFromDate && d <= heatmapToDate) rangeDateIndices.add(i);
    }});

    // Aggregate: employee x dow for ALL employees
    var empCount = DATA.employees.length;
    var z = [];
    for (var e = 0; e < empCount; e++) {{
        z.push([0,0,0,0,0,0,0]);
    }}

    DATA.records.forEach(function(rec) {{
        if (!isSelected(rec)) return;
        if (!rangeDateIndices.has(rec[0])) return;
        z[rec[3]][rec[2]] += 1;
    }});

    // Build paired array with totals for sorting
    var paired = DATA.employees.map(function(name, i) {{
        var total = z[i].reduce(function(a, b) {{ return a + b; }}, 0);
        return {{ name: name, row: z[i], total: total }};
    }});

    // Sort: active employees first (desc by total), then zero-activity alphabetically
    paired.sort(function(a, b) {{
        if (a.total > 0 && b.total > 0) return b.total - a.total;
        if (a.total > 0) return -1;
        if (b.total > 0) return 1;
        return a.name.localeCompare(b.name);
    }});

    var sortedNames = paired.map(function(p) {{ return p.name; }});
    var sortedZ = paired.map(function(p) {{ return p.row; }});

    // Build background color matrix: #EFFD5F for zero-activity rows, white otherwise
    // This is rendered as a second heatmap trace behind the main data trace
    var bgZ = [];
    var zeroSet = new Set();
    paired.forEach(function(p, i) {{
        if (p.total === 0) {{
            bgZ.push([1,1,1,1,1,1,1]);
            zeroSet.add(i);
        }} else {{
            bgZ.push([0,0,0,0,0,0,0]);
        }}
    }});

    var chartHeight = Math.max(450, sortedNames.length * 28 + 100);

    var traces = [];

    // Background trace: highlights zero-activity rows
    if (zeroSet.size > 0) {{
        traces.push({{
            x: dowLabels,
            y: sortedNames,
            z: bgZ,
            type: 'heatmap',
            colorscale: [[0, '#ffffff'], [1, '#EFFD5F']],
            zmin: 0,
            zmax: 1,
            showscale: false,
            hoverinfo: 'skip'
        }});
    }}

    // Main data trace
    traces.push({{
        x: dowLabels,
        y: sortedNames,
        z: sortedZ,
        type: 'heatmap',
        colorscale: [[0, 'rgba(255,255,255,0)'], [0.001, 'rgba(255,255,255,0)'], [0.001, '#c8e6c9'], [0.25, '#c8e6c9'], [0.5, '#66bb6a'], [0.75, '#2e7d32'], [1, '#1b5e20']],
        zmin: 0,
        hovertemplate: '%{{y}}<br>%{{x}}: %{{z}} changes<extra></extra>'
    }});

    Plotly.react('chart-heatmap', traces, Object.assign({{}}, plotlyLayout, {{
        margin: {{ l: 200, r: 30, t: 40, b: 60 }},
        yaxis: {{ autorange: 'reversed', tickfont: {{ size: 12 }} }},
        height: chartHeight
    }}), plotlyConfig);
}}

// ---------------------------------------------------------------------------
// Render all
// ---------------------------------------------------------------------------
function renderAll() {{
    renderDaily();
    renderDow();
    renderTypes();
    renderHeatmap();
}}

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
