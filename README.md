# Jira Automation & Reporting Server

A comprehensive FastAPI-based server for automating Jira workflows, performing data analysis, and generating reports. Designed to run locally on macOS with jobs triggered via REST API endpoints and scheduled through cron.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Setup and Installation](#setup-and-installation)
- [Module Documentation](#module-documentation)
  - [Data Analysis Modules](#data-analysis-modules)
  - [Automation Modules](#automation-modules)
  - [Burndown & Reporting Modules](#burndown--reporting-modules)
- [API Endpoints](#api-endpoints)
- [Scheduled Tasks (Cron)](#scheduled-tasks-cron)
- [Database Schema](#database-schema)
- [Configuration](#configuration)
- [Development Guidelines](#development-guidelines)

---

## Overview

This project provides a centralized automation platform for:

- **ETL Processing**: Syncing Jira data to PostgreSQL for analytics
- **Initiative Tracking**: Mapping epics/initiatives to child issues with automatic closure detection
- **Burndown Analysis**: Generating burndown charts for COMPDIV and IRIS initiatives
- **Bug Tracking**: Monitoring bug trends, escaped bugs, and customer-impacting issues
- **Quality Assurance**: Data quality reports, RCA sub-task creation, and aging ticket detection
- **Team Reporting**: Daily push reports, manager reports, and investment trend analysis

### Key Features

- **RESTful API**: All jobs exposed as POST endpoints
- **Background Processing**: Async task execution with FastAPI BackgroundTasks
- **Centralized Logging**: YAML-based configuration with custom log levels
- **Database-Backed**: PostgreSQL for persistent storage and historical analysis
- **Scheduled Automation**: Cron integration for daily/weekly jobs
- **Interactive Dashboards**: HTML dashboards with tabbed navigation for burndown charts

---

## Architecture

### High-Level Design

```
┌─────────────────┐
│   Cron Jobs     │ (scheduled triggers)
└────────┬────────┘
         │
         v
┌─────────────────────────────────────────────────────┐
│              FastAPI Server (main.py)               │
│  ┌──────────────────────────────────────────────┐  │
│  │     API Endpoints (POST /jobs/*)             │  │
│  └──────────────┬───────────────────────────────┘  │
│                 │                                   │
│                 v                                   │
│  ┌──────────────────────────────────────────────┐  │
│  │   Task Orchestration (tasks.py)              │  │
│  └──────────────┬───────────────────────────────┘  │
└─────────────────┼───────────────────────────────────┘
                  │
         ┌────────┴─────────┐
         │                  │
         v                  v
┌─────────────────┐  ┌──────────────────┐
│ Data Analysis   │  │ Jira Automation  │
│   Modules       │  │     Modules      │
│                 │  │                  │
│ • ETL/Sync      │  │ • Icebox Mgmt    │
│ • Initiative    │  │ • RCA Creation   │
│   Analysis      │  │ • Bug Tracking   │
│ • Investment    │  │ • Burndown       │
│   Trends        │  │ • Reporting      │
└─────────┬───────┘  └────────┬─────────┘
          │                   │
          └───────┬───────────┘
                  │
                  v
         ┌────────────────┐
         │  PostgreSQL    │
         │   Database     │
         └────────────────┘
         ┌────────────────┐
         │  Jira REST API │
         └────────────────┘
```

### Data Flow

1. **API Request** → FastAPI endpoint receives POST request
2. **Task Scheduling** → Background task queued via `BackgroundTasks`
3. **Business Logic** → Task module executes (ETL, analysis, automation)
4. **External I/O** → Calls to Jira API and PostgreSQL database
5. **Artifact Generation** → CSV/HTML reports written to disk
6. **Logging** → Structured logs written to rotating file handlers

---

## Project Structure

```
jira_server/
├── .env                           # Environment configuration (secrets, JQL, paths)
├── main.py                        # FastAPI app definition and REST endpoints
├── tasks.py                       # Task orchestration layer
├── logging_config.py              # Logging setup with custom levels
├── logging_utils.py               # Logger helpers and decorators
├── log_config.yaml                # YAML logging configuration
├── requirements.txt               # Python dependencies
├── run_app.sh                     # Server startup script
├── venv/                          # Python virtual environment (gitignored)
│
├── logs/                          # Application and cron job logs
│   ├── app.log                    # Main application log (rotating)
│   ├── access.log                 # HTTP access log
│   └── cron_*.log                 # Individual cron job logs
│
├── reports/                       # Generated reports and dashboards
│   ├── *.csv                      # Data quality and analysis reports
│   ├── *.html                     # Push reports and summaries
│   └── compdiv_burndown/          # Burndown charts directory
│       ├── dashboard.html         # Master burndown dashboard
│       ├── COMPDIV-*_burndown.html
│       ├── IRIS_*_burndown.html
│       └── COMPLANG-*_burndown.html
│
├── helper_files/
│   └── customer_support_lvls.json # Customer analysis configuration
│
├── jira_data_analysis/            # Data ETL and analysis
│   ├── __init__.py
│   ├── db_utils.py                # Database connection pooling
│   ├── jira_processor.py          # Jira data ETL and sync
│   ├── jira_utils.py              # Common Jira utilities
│   ├── initiative_children.py     # Initiative hierarchy mapping
│   └── investment_trends.py       # Investment analysis
│
├── jira_automation/               # Jira automation and reporting
│   ├── __init__.py
│   ├── jira_icebox.py             # Icebox management automation
│   ├── create_rca_subtasks.py     # RCA sub-task creation
│   ├── customer_analysis.py       # Customer bug tracking
│   ├── data_quality_report.py     # Data quality monitoring
│   ├── daily_pushes.py            # Daily push report generation
│   ├── compdiv_burndown.py        # COMPDIV burndown analysis
│   ├── iris_burndown.py           # IRIS burndown analysis
│   ├── generate_burndown_dashboard.py  # Dashboard HTML generation
│   ├── collect_bug_snapshots.py   # Bug trending data collection
│   ├── generate_bug_charts.py     # Bug trend chart generation
│   ├── derive_platform_version.py # Platform version derivation
│   └── ldap_manager_report.py     # Manager hierarchy report
│
├── run_*.sh                       # Individual job trigger scripts
└── create_iris_burndown_table.py  # Database table setup utility
```

---

## Setup and Installation

### Prerequisites

- **Python 3.10+**
- **PostgreSQL 12+** (running instance with credentials)
- **macOS** (designed for local execution on macOS)
- **Jira Personal Access Token** (for API authentication)

### 1. Clone and Navigate

```bash
cd /path/to/jira_server
```

### 2. Environment Configuration

Create `.env` file in the `jira_server/` root directory:

```bash
# Jira API Credentials
JIRA_URL="https://your-jira-instance.com"
JIRA_TOKEN="your_personal_access_token"

# Database Connection
DATABASE_URL="postgresql://user:password@host:port/dbname"

# Project Configuration
JIRA_PROJECTS="COMPDIV,COMPLANG,COMPHOST"
JIRA_REPORT_DIR="./reports"

# Initiative Analysis
JIRA_INITIATIVE_JQL="project = COMPDIV AND type = Epic AND labels in (compdiv-initiative)"
JIRA_IRIS_LABELS="iris,iris-initiative"

# Burndown Configuration
COMPDIV_BURNDOWN_DIR="/path/to/burndown/output"
COMPDIV_FILTER_FLAG=""           # Optional: filter epics by flag
COMPDIV_MAX_LOOKAHEAD_DAYS="365" # Prediction horizon

# Bug Tracking
BUG_SNAPSHOT_DB_TABLE="bug_snapshots"

# Data Quality JQL Queries
JQL_MISSING_FIXVER="project in (COMPDIV) AND fixVersion is EMPTY"
JQL_MISSING_ORIGIN="project in (COMPDIV) AND \"Origin\" is EMPTY"
# ... (additional JQL queries)

# Paths
JIRA_CUSTOMER_JSON_PATH="helper_files/customer_support_lvls.json"
```

See `CLAUDE.md` for full list of environment variables.

### 3. Database Setup

Create required tables:

```bash
# Create IRIS burndown table
python create_iris_burndown_table.py

# Additional tables are created automatically on first run
# or can be created manually from schema documentation
```

### 4. Start the Server

```bash
./run_app.sh
```

This script:
- Creates a virtual environment (if needed)
- Installs dependencies from `requirements.txt`
- Activates the venv
- Starts Uvicorn server on `http://127.0.0.1:8000`

### 5. Verify Installation

```bash
# Check health
curl http://127.0.0.1:8000/health

# View API documentation
open http://127.0.0.1:8000/docs
```

---

## Module Documentation

### Data Analysis Modules

Located in `jira_data_analysis/`

#### `jira_processor.py`
**Purpose**: Core ETL module for syncing Jira data to PostgreSQL

**Key Functions**:
- `build_daily_jql()`: Constructs JQL for incremental daily sync
- `fetch_all_issues()`: Paginated Jira issue retrieval
- `process_and_load_issues()`: Transforms and loads issues to database
- `get_required_field_list()`: Dynamically determines needed Jira fields

**Database Tables**: `jira_data`, `tbl_jira_sprint_data`

**Trigger**: `/jobs/daily` endpoint

---

#### `initiative_children.py`
**Purpose**: Maps initiative/epic relationships to child issues with recursive BFS traversal

**Key Functions**:
- `sync_initiatives_from_jql()`: Syncs new initiatives from JQL, marks as IRIS based on labels
- `close_completed_iris_initiatives()`: **NEW** - Automatically closes IRIS initiatives when statusCategory = Done
- `collect_issue_keys_for_epic()`: Recursively discovers all child issues (max depth 10)
- `store_issues_bulk()`: Bulk inserts/updates child issues

**Database Tables**:
- `tbl_initiative_issue_keys` (parent epics)
- `tbl_initiative_children` (child issues)

**Key Features**:
- **IRIS Detection**: Checks issue labels against `JIRA_IRIS_LABELS` env var
- **Automatic Closure**: Runs daily to mark completed IRIS epics as inactive
- **Relationship Types**: Follows "Is Child", "Is Parent", "Relates", "Hierarchy" links

**Trigger**: `/jobs/release` or daily when release is due

---

#### `investment_trends.py`
**Purpose**: Analyzes story point investment across initiatives, bugs, and operational work

**Key Functions**:
- `calculate_investment_totals()`: Aggregates points by category
- `generate_trend_report()`: Creates CSV report of investment breakdown

**Output**: CSV report showing initiative vs bug vs operational investment percentages

**Trigger**: `/jobs/release`

---

#### `db_utils.py`
**Purpose**: Database connection pooling and common utilities

**Key Functions**:
- `get_connection_pool()`: Returns psycopg2 connection pool (1-20 connections)
- `load_sprint_managers()`: Caches project owner mappings
- `release_run_check()`: Determines if release analysis should run
- `update_run_log()`: Logs job execution for scheduling logic

**Connection Pool**: Singleton pattern, initialized on first import

---

### Automation Modules

Located in `jira_automation/`

#### `jira_icebox.py`
**Purpose**: Automated icebox management - moves stale issues to icebox status

**Key Functions**:
- `find_stale_issues()`: Queries Jira for issues meeting icebox criteria
- `move_to_icebox()`: Updates issue status and adds comment

**Criteria**: Configurable via JQL in `.env`

**Trigger**: `/jobs/jiraicebox` (daily via cron)

---

#### `create_rca_subtasks.py`
**Purpose**: Automatically creates Root Cause Analysis sub-tasks for critical bugs

**Key Functions**:
- `find_rca_candidates()`: Searches for escaped bugs without RCA sub-tasks
- `create_rca_subtask()`: Creates standardized RCA sub-task with checklist

**Criteria**:
- Bug type
- Priority/Severity thresholds
- Origin field (escaped bugs)
- Created after `JIRA_CREATED_DATE`

**Trigger**: `/jobs/create-rca-subtasks`

---

#### `customer_analysis.py`
**Purpose**: Monitors and reports on customer-impacting bugs

**Key Functions**:
- `find_customer_bugs()`: Identifies bugs with customer labels/components
- `update_customer_fields()`: Adds customer support level labels
- `generate_customer_report()`: Creates CSV report of open customer issues

**Configuration**: `helper_files/customer_support_lvls.json`

**Trigger**: `/jobs/customer-analysis`

---

#### `data_quality_report.py`
**Purpose**: Generates reports on missing/invalid Jira data

**Key Functions**:
- `fetch_issues_for_report()`: Executes JQL queries for data gaps
- `check_invalid_fix_versions_for_done_issues()`: Validates fix version format (YYYY.MM)
- `write_consolidated_report()`: Outputs findings to CSV and sends Teams notifications

**Checks**:
- Missing fix versions
- Invalid fix versions for Done issues (not matching YYYY.MM pattern)
- Missing origin/root cause
- Missing pipeline discovery stage
- Missing platform version
- Missing affects version

**Project Exclusion**:
- Environment variable `DATA_QUALITY_EXCLUDE_PROJECTS` allows excluding specific projects
- Example: `DATA_QUALITY_EXCLUDE_PROJECTS="SIGNOFF,TESTPROJ"`
- Automatically adds `AND project NOT IN (...)` to all JQL queries

**Output**:
- CSV report: `reports/data_quality_report_YYYY-MM-DD.csv`
- Teams notifications sent to managers with actionable items
- Unassigned issues sent to fallback contact

**Trigger**: `/jobs/data-quality-report`

---

#### `daily_pushes.py`
**Purpose**: Generates HTML report of recently merged pull requests

**Key Functions**:
- `find_recent_pushes()`: Searches Jira for issues with recent PR activity
- `build_html_report()`: Creates formatted HTML table

**Output**: `reports/daily_pushes.html`

**Trigger**: `/jobs/daily-pushes` (9:15 AM daily)

---

### Burndown & Reporting Modules

#### `compdiv_burndown.py`
**Purpose**: COMPDIV initiative burndown analysis with BFS traversal

**Algorithm**:
1. Load epic keys from `tbl_initiative_issue_keys` (filter by `COMPDIV-*` pattern)
2. For each epic:
   - Fetch issues directly in epic (via Epic Link)
   - Recursively follow Parent/Child links (BFS, max depth 6)
   - When encountering another epic, include its children
   - Safety limit: 5000 nodes max
3. Calculate open story points by type (Bug/Story/Task-Research)
4. Store daily snapshot in `tbl_compdiv_burndown`
5. Generate HTML chart with linear regression prediction

**Key Functions**:
- `collect_issue_keys_for_epic()`: BFS traversal with epic-in-epic handling
- `compute_point_totals()`: Aggregates points, respects statusCategory
- `run_for_all_compdiv_epics()`: Processes all epics, writes HTML files
- `build_plot_html()`: Creates Plotly chart with 80% CI prediction

**Database Tables**:
- `tbl_compdiv_burndown` (time series data)
- `tbl_initiative_issue_keys` (epic source list)

**Output**: `{epic_key}_burndown.html` files

**Trigger**: `/jobs/compdiv-burndown`

---

#### `iris_burndown.py` 🆕
**Purpose**: IRIS initiative burndown analysis (identical methodology to COMPDIV)

**Key Differences from COMPDIV**:
- Queries `tbl_initiative_issue_keys WHERE "IRIS" = true AND active_flag IS NULL`
- Stores data in `tbl_iris_burndown` table
- Outputs files with `IRIS_` prefix: `IRIS_{epic_key}_burndown.html`
- Uses `IRIS_TRACE` and `IRIS_SKIP_HTML` env vars

**Algorithm**: Same BFS traversal as COMPDIV burndown

**Database Tables**:
- `tbl_iris_burndown` (time series data)
- `tbl_initiative_issue_keys` (filtered by IRIS flag)

**Output**: `IRIS_{epic_key}_burndown.html` files in same directory as COMPDIV

**Trigger**: `/jobs/iris-burndown`

---

#### `generate_burndown_dashboard.py`
**Purpose**: Creates unified HTML dashboard with tabbed interface for all burndown charts

**Architecture**:
```
Dashboard (3 Tabs)
├── Overview Tab: COMPDIV-* files (non-IRIS)
├── BIGINT Tab: COMPLANG-*, COMPHOST-* files
└── IRIS Tab: IRIS_* files (IRIS initiatives)
```

**Key Functions**:
- `collect_html_files()`: Scans directory, categorizes by filename prefix
- `extract_epic_title()`: Parses Plotly HTML for display names
- `generate_html_structure()`: Builds responsive 3-column grid layout

**Features**:
- Tab switching with lazy iframe loading
- Responsive grid (3 cols → 2 cols → 1 col on smaller screens)
- Open in new tab links
- Automatic legend fix via iframe reload

**Output**: `dashboard.html` in `COMPDIV_BURNDOWN_DIR`

**Trigger**: `/jobs/generate-burndown-dashboard`

---

#### `collect_bug_snapshots.py`
**Purpose**: Daily collection of bug counts for trend analysis

**Key Functions**:
- `collect_snapshot()`: Queries Jira for bug counts by status/priority
- `store_snapshot()`: Inserts time-series data into database

**Database Tables**: `bug_snapshots` (time-series)

**Trigger**: `/jobs/collect-bug-snapshots`

---

#### `generate_bug_charts.py`
**Purpose**: Generates Plotly charts from bug snapshot data

**Key Functions**:
- `fetch_snapshot_data()`: Retrieves time-series from database
- `build_trend_charts()`: Creates line charts for bug metrics

**Output**: HTML files with bug trend visualizations

**Trigger**: `/jobs/generate-bug-charts`

---

#### `derive_platform_version.py`
**Purpose**: Derives platform version field for bugs based on fix version patterns

**Key Functions**:
- `parse_version()`: Extracts version number from fix version string
- `update_platform_version()`: Bulk updates Jira issues

**Trigger**: `/jobs/derive-platform-version` (part of data quality workflow)

---

#### `ldap_manager_report.py`
**Purpose**: Generates manager hierarchy reports from LDAP data

**Key Functions**:
- `fetch_ldap_hierarchy()`: Queries LDAP for reporting relationships
- `generate_manager_report()`: Creates CSV report of team structure

**Database Tables**: `ldap_hierarchy`

**Trigger**: `/jobs/ldap-report`

---

## API Endpoints

All endpoints return `202 Accepted` and run tasks in the background.

### Data Sync & Analysis

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/jobs/daily` | POST | Daily Jira data sync + IRIS closure check |
| `/jobs/release` | POST | Full release analysis (initiatives + trends) |

### Burndown & Tracking

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/jobs/compdiv-burndown` | POST | Run COMPDIV burndown for all epics |
| `/jobs/iris-burndown` | POST | Run IRIS burndown for active IRIS epics |
| `/jobs/generate-burndown-dashboard` | POST | Generate master dashboard HTML |
| `/jobs/collect-bug-snapshots` | POST | Collect daily bug snapshot data |
| `/jobs/generate-bug-charts` | POST | Generate bug trend charts from snapshots |

### Automation & Quality

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/jobs/jiraicebox` | POST | Run icebox automation |
| `/jobs/create-rca-subtasks` | POST | Create RCA sub-tasks for critical bugs |
| `/jobs/customer-analysis` | POST | Update and report on customer bugs |
| `/jobs/data-quality-report` | POST | Generate data quality CSV report |
| `/jobs/derive-platform-version` | POST | Derive platform versions for bugs |

### Reporting

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/jobs/daily-pushes` | POST | Generate daily push report HTML |
| `/jobs/ldap-report` | POST | Generate manager hierarchy report |

### Utility

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/docs` | GET | OpenAPI documentation (Swagger UI) |

### Example Usage

```bash
# Trigger daily sync
curl -X POST http://127.0.0.1:8000/jobs/daily

# Run IRIS burndown
curl -X POST http://127.0.0.1:8000/jobs/iris-burndown

# Generate dashboard
curl -X POST http://127.0.0.1:8000/jobs/generate-burndown-dashboard
```

---

## Scheduled Tasks (Cron)

### macOS Setup

1. **Grant Full Disk Access to Terminal/Cron**:
   - System Settings → Privacy & Security → Full Disk Access
   - Add Terminal.app

2. **Edit Crontab**:
   ```bash
   crontab -e
   ```

### Recommended Schedule

```cron
# Daily data sync and icebox (9:00 AM weekdays)
0 9 * * 1-5 /Users/wegelpi/github_repos/sas-jira/jira_server/run_daily_job.sh
0 9 * * 1-5 /Users/wegelpi/github_repos/sas-jira/jira_server/run_icebox_job.sh

# Daily push report (9:15 AM weekdays)
15 9 * * 1-5 /Users/wegelpi/github_repos/sas-jira/jira_server/run_pushes_job.sh

# COMPDIV burndown (10:00 AM weekdays)
0 10 * * 1-5 /Users/wegelpi/github_repos/sas-jira/jira_server/run_compdiv_burndown.sh

# IRIS burndown (10:30 AM weekdays)
30 10 * * 1-5 /Users/wegelpi/github_repos/sas-jira/jira_server/run_iris_burndown.sh

# Dashboard generation (11:00 AM weekdays)
0 11 * * 1-5 /Users/wegelpi/github_repos/sas-jira/jira_server/run_burndown_dashboard.sh

# Weekly data quality report (Monday 8:00 AM)
0 8 * * 1 /Users/wegelpi/github_repos/sas-jira/jira_server/run_data_quality.sh

# Customer analysis (Monday/Thursday 9:00 AM)
0 9 * * 1,4 /Users/wegelpi/github_repos/sas-jira/jira_server/run_customer_analysis.sh
```

### Shell Script Pattern

All `run_*.sh` scripts follow this pattern:

```bash
#!/bin/bash
PROJECT_DIR="/Users/wegelpi/github_repos/sas-jira/jira_server"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/cron_jobname.log"
TIMESTAMP=$(date +"%Y-%m-%d %T")

mkdir -p "$LOG_DIR"

echo "---" >> "$LOG_FILE"
echo "[$TIMESTAMP] Cron job started: Triggering /jobs/endpoint..." >> "$LOG_FILE"

/usr/bin/curl -s -X POST http://127.0.0.1:8000/jobs/endpoint >> "$LOG_FILE" 2>&1

echo "[$TIMESTAMP] Cron job finished." >> "$LOG_FILE"
```

---

## Database Schema

### Core Tables

#### `jira_data` / `tbl_jira_sprint_data`
Main fact table for Jira issues (daily snapshots).

**Key Columns**:
- `issue_key` (VARCHAR): Jira issue key
- `issue_type`, `issue_status`, `priority`
- `story_points` (NUMERIC)
- `sprint_name`, `epic_link`, `issue_parent`
- `update_date` (TIMESTAMP)
- `run_flag` (VARCHAR): 'daily' or 'RELEASE'

---

#### `tbl_initiative_issue_keys`
Stores initiative/epic metadata for burndown analysis.

**Key Columns**:
- `issue_key` (VARCHAR, PK): Epic key
- `eff_start_date`, `eff_end_date` (DATE): Effective date range
- `"IRIS"` (BOOLEAN): IRIS initiative flag
- `active_flag` (BOOLEAN): Active status (NULL = active, false = closed)
- `filter_flag` (CHAR(7)): Optional filtering

**Updated By**: `initiative_children.sync_initiatives_from_jql()`

**IRIS Closure Logic**: `initiative_children.close_completed_iris_initiatives()` runs daily:
- Queries active IRIS epics (`"IRIS" = true AND active_flag IS NULL`)
- Checks Jira statusCategory for each
- Sets `eff_end_date = CURRENT_DATE` and `active_flag = false` if closed

---

#### `tbl_initiative_children`
Maps initiative epics to all related child issues.

**Key Columns**:
- `initiative_issue_key` (VARCHAR): Parent epic key
- `issue_key` (VARCHAR): Child issue key
- `summary`, `issue_type`, `status`, `assignee`
- `story_points` (NUMERIC)
- `effective_dttm` (TIMESTAMP): Last updated

**Updated By**: `initiative_children.store_issues_bulk()`

---

#### `tbl_compdiv_burndown`
Time-series burndown data for COMPDIV epics.

**Schema**:
```sql
CREATE TABLE tbl_compdiv_burndown (
    run_date DATE NOT NULL,
    epic_key VARCHAR(50) NOT NULL,
    bug_points NUMERIC(10,2),
    story_points NUMERIC(10,2),
    task_research_points NUMERIC(10,2),
    total_points NUMERIC(10,2),
    PRIMARY KEY (run_date, epic_key)
);
```

**Updated By**: `compdiv_burndown.upsert_burndown_row()`

---

#### `tbl_iris_burndown` 🆕
Time-series burndown data for IRIS initiatives (same schema as COMPDIV).

**Schema**:
```sql
CREATE TABLE tbl_iris_burndown (
    run_date DATE NOT NULL,
    epic_key VARCHAR(50) NOT NULL,
    bug_points NUMERIC(10,2),
    story_points NUMERIC(10,2),
    task_research_points NUMERIC(10,2),
    total_points NUMERIC(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_date, epic_key)
);
```

**Created By**: `create_iris_burndown_table.py`

**Updated By**: `iris_burndown.upsert_burndown_row()`

---

#### `bug_snapshots`
Daily snapshot of bug counts for trend analysis.

**Key Columns**:
- `snapshot_date` (DATE)
- `status`, `priority`
- `bug_count` (INTEGER)

**Updated By**: `collect_bug_snapshots.main()`

---

#### `tbl_run_log`
Execution log for job scheduling logic.

**Key Columns**:
- `execOrigin` (VARCHAR): Execution source
- `startDTTM`, `endDTTM` (TIMESTAMP)
- `runType` (VARCHAR): 'DAILY', 'RELEASE'

**Updated By**: `db_utils.update_run_log()`

**Used By**: `db_utils.release_run_check()` to determine if release analysis should run

---

### Custom Fields Reference

| Field ID | Field Name | Usage |
|----------|------------|-------|
| `customfield_10301` | Epic Link | Links issues to parent epic |
| `customfield_16301` | Parent Link | Alternative parent relationship |
| `customfield_10102` | Sprint | Sprint assignment |
| `customfield_15600` | Pipeline Stage | Development stage |
| `customfield_14504` | Bug Origin | Escaped bug flag |
| `customfield_15703` | Requirement/Epic | Initiative association |
| `customfield_10002` | Story Points | Estimation field |

Use `get_jira_fields.py` to discover field IDs in your Jira instance.

---

## Configuration

### Environment Variables

Comprehensive list in `.env`:

```bash
# === JIRA API ===
JIRA_URL="https://your-jira.com"
JIRA_TOKEN="your_token"
JIRA_PROJECTS="COMPDIV,COMPLANG,COMPHOST"
JIRA_TIMEOUT_SECONDS="30"

# === DATABASE ===
DATABASE_URL="postgresql://user:pass@host:5432/dbname"

# === INITIATIVE TRACKING ===
JIRA_INITIATIVE_JQL="project = COMPDIV AND type = Epic AND labels in (initiative)"
JIRA_IRIS_LABELS="iris,iris-initiative"

# === BURNDOWN ===
COMPDIV_BURNDOWN_DIR="/path/to/burndown/charts"
COMPDIV_FILTER_FLAG=""              # Optional epic filtering
COMPDIV_MAX_LOOKAHEAD_DAYS="365"    # Prediction horizon (days)
COMPDIV_TRACE="*"                   # Debug: trace all epics
COMPDIV_SKIP_HTML="false"           # Skip HTML generation

IRIS_TRACE=""                       # Debug: IRIS epic tracing
IRIS_SKIP_HTML="false"
IRIS_MAX_LOOKAHEAD_DAYS="365"

# === REPORTING ===
JIRA_REPORT_DIR="./reports"
HOMEPAGE_REPORTS_DIR="/path/to/homepage/reports/"

# === DATA QUALITY ===
DATA_QUALITY_EXCLUDE_PROJECTS="SIGNOFF"  # Comma-separated list of projects to exclude
DATA_QUALITY_FALLBACK_NAME="Manager Name"
DATA_QUALITY_FALLBACK_EMAIL="manager@company.com"

# === DATA QUALITY JQL ===
JQL_MISSING_FIXVER="project in (COMPDIV) AND fixVersion is EMPTY"
JQL_MISSING_ORIGIN="project in (COMPDIV) AND \"Origin\" is EMPTY"
JQL_UNESTIMATED="project = COMPDIV AND type = Story AND \"Story Points\" is EMPTY"
# ... (additional JQL queries)

# === CUSTOMER ANALYSIS ===
JIRA_CUSTOMER_JSON_PATH="helper_files/customer_support_lvls.json"

# === RCA SUBTASKS ===
JIRA_RCA_ORIGIN_FIELD_NAME="Origin"
JIRA_CREATED_DATE="2025-01-01"

# === PUSH REPORTS ===
JIRA_PUSH_REPORT_DAYS="7"

# === LDAP ===
LDAP_SERVER="ldap://ldap.company.com"
LDAP_BASE_DN="dc=company,dc=com"
```

---

## Development Guidelines

### Logging Standards

**Import Pattern**:
```python
from logging_utils import get_logger, log_section_header

logger = get_logger(__name__)
```

**Custom Log Levels**:
```python
logger.start("Task starting")          # Task initiation
logger.processing("Processing data")   # Data processing
logger.database("Updating database")   # DB operations
logger.searching("Searching Jira")     # API queries
logger.connecting("Connecting to X")   # Connection attempts
logger.success("Task completed")       # Success status
logger.complete("Task done", duration) # Task completion with duration
```

**Section Headers**:
```python
log_section_header(logger, "INITIATIVE ANALYSIS")
# Creates visually distinct header in logs
```

### Adding New Endpoints

1. **Create Task Function** in `tasks.py`:
   ```python
   def run_new_feature_task():
       log_section_header(logger, "NEW FEATURE")
       logger.start("Starting new feature task")
       try:
           new_module.main()
           logger.complete("New feature completed")
       except Exception as e:
           logger.exception(f"Error in new feature: {e}")
   ```

2. **Add API Endpoint** in `main.py`:
   ```python
   @app.post("/jobs/new-feature", status_code=202, summary="Trigger New Feature")
   async def trigger_new_feature(background_tasks: BackgroundTasks):
       logger.info("New feature endpoint triggered via API")
       background_tasks.add_task(run_new_feature_task)
       logger.success("New feature scheduled")
       return {"message": "New feature started", "status": "scheduled"}
   ```

3. **Create Shell Script** (optional):
   ```bash
   # run_new_feature.sh
   #!/bin/bash
   curl -X POST http://127.0.0.1:8000/jobs/new-feature
   ```

### Database Queries

**Always use connection pooling**:
```python
from jira_data_analysis import db_utils

pool = db_utils.get_connection_pool()
conn = pool.getconn()
try:
    with conn.cursor() as cur:
        cur.execute("SELECT ...")
        results = cur.fetchall()
    conn.commit()
finally:
    pool.putconn(conn)
```

### Jira API Best Practices

1. **Use centralized client**:
   ```python
   from tasks import get_jira_client
   jira = get_jira_client()
   ```

2. **Batch queries**:
   ```python
   # Good: Single query with IN clause
   jql = f"key in ({','.join(keys)})"
   issues = jira.search_issues(jql, maxResults=200)

   # Bad: Individual queries in loop
   for key in keys:
       issue = jira.issue(key)  # Avoid!
   ```

3. **Specify required fields**:
   ```python
   fields = "summary,status,assignee,customfield_10002"
   issues = jira.search_issues(jql, fields=fields)
   ```

### Code Style

- **Function Docstrings**: Always include purpose, parameters, return values
- **Type Hints**: Use for function signatures
- **Constants**: Define at module top in UPPER_CASE
- **Error Handling**: Always use try/except with logger.exception()
- **Commits**: Include context in commit messages (see CLAUDE.md)

---

## Troubleshooting

### Common Issues

**1. Database Connection Errors**
```bash
# Verify DATABASE_URL in .env
# Check PostgreSQL is running
psql "$DATABASE_URL" -c "SELECT 1"
```

**2. Missing Tables**
```bash
# Create IRIS burndown table
python create_iris_burndown_table.py

# Check other tables exist
psql "$DATABASE_URL" -c "\dt"
```

**3. Jira API Timeouts**
```bash
# Increase timeout in .env
JIRA_TIMEOUT_SECONDS="60"
```

**4. Cron Jobs Not Running**
- Check Full Disk Access in macOS System Settings
- Verify absolute paths in shell scripts
- Check cron logs: `tail -f logs/cron_*.log`

**5. Empty IRIS Tab in Dashboard**
- Verify IRIS initiatives exist: `SELECT * FROM tbl_initiative_issue_keys WHERE "IRIS" = true`
- Check HTML files have `IRIS_` prefix: `ls $COMPDIV_BURNDOWN_DIR/IRIS_*.html`
- Regenerate dashboard: `curl -X POST http://127.0.0.1:8000/jobs/generate-burndown-dashboard`

---

## License

Internal use only - SAS Institute Inc.

---

## Support

For questions or issues, contact the project maintainer or file an issue at:
https://github.com/anthropics/claude-code/issues (for Claude Code-specific questions)
