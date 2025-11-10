# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a FastAPI-based Jira automation and reporting server designed to run locally on macOS. It provides automated workflows for Jira data analysis, ETL processing, bug tracking, and report generation. The server exposes RESTful API endpoints that are triggered via curl commands, typically scheduled through cron jobs.

**Key purpose**: Automate Jira data synchronization to PostgreSQL, generate analytics reports (CSV/HTML), and perform automated Jira actions (e.g., creating RCA sub-tasks, icebox management).

## Architecture

### High-Level Structure

The project follows a layered architecture:

1. **API Layer** (`jira_server/main.py`): FastAPI application exposing POST endpoints for job triggers
2. **Task Orchestration** (`jira_server/tasks.py`): Background task runners that coordinate between API and business logic
3. **Business Logic Packages**:
   - `jira_data_analysis/`: ETL and analytics (database sync, initiative analysis, investment trends)
   - `jira_automation/`: Jira actions (icebox management, RCA creation, customer analysis, burndown charts)
4. **Shared Utilities**:
   - `db_utils.py`: PostgreSQL connection pooling and database operations
   - `logging_utils.py` + `logging_config.py`: Centralized logging with custom log levels
   - `jira_utils.py`: Common Jira API utilities

### Key Design Patterns

- **Background Tasks**: All job endpoints (e.g., `/jobs/daily`) use FastAPI's BackgroundTasks to run operations asynchronously
- **Connection Pooling**: Database connections are managed through psycopg2's SimpleConnectionPool (1-20 connections)
- **Centralized Logging**: YAML-based logging configuration (`log_config.yaml`) with custom log levels (`.start()`, `.complete()`, `.success()`, `.processing()`)
- **Environment-Driven Config**: All secrets and settings in `jira_server/.env` (Jira credentials, database URL, JQL queries)

### Critical Data Flow

1. **Daily Sync**: `/jobs/daily` → `run_jira_export_task()` → `jira_processor.build_daily_jql()` fetches issues updated since last run → stores in PostgreSQL
2. **Release Analysis**: Triggered automatically when release run is due (checked via `db_utils.release_run_check()`) or manually via `/jobs/release`
3. **Initiative Analysis**: Maps initiative/epic relationships to child issues, stored in database for reporting

## Development Commands
- Every change should be accompanied by a suggested and concise commit message that accurately describes the change being proposed

### Server Management

```bash
# Start the FastAPI server (from jira_server/ directory)
./run_app.sh
# This script activates venv, installs dependencies, and runs uvicorn

# Access API documentation
# Navigate to http://127.0.0.1:8000/docs

# Check server health
curl http://127.0.0.1:8000/health
```

### Running Jobs

All jobs are triggered via POST to the running server:

```bash
# Daily data sync (fetches Jira issues updated since last run)
curl -X POST http://127.0.0.1:8000/jobs/daily

# Full release analysis (initiative mapping + investment trends)
curl -X POST http://127.0.0.1:8000/jobs/release

# Icebox automation (moves stale issues)
curl -X POST http://127.0.0.1:8000/jobs/jiraicebox

# Generate daily push report (issues with recent PRs)
curl -X POST http://127.0.0.1:8000/jobs/daily-pushes

# Create RCA sub-tasks for critical bugs
curl -X POST http://127.0.0.1:8000/jobs/create-rca-subtasks

# Customer bug analysis (finds/updates customer-labeled bugs)
curl -X POST http://127.0.0.1:8000/jobs/customer-analysis

# Data quality report (missing fixVersions, Origins, etc.)
curl -X POST http://127.0.0.1:8000/jobs/data-quality-report

# COMPDIV burndown for all epics
curl -X POST http://127.0.0.1:8000/jobs/compdiv-burndown

# Bug snapshot collection (daily time-series data)
curl -X POST http://127.0.0.1:8000/jobs/collect-bug-snapshots

# Generate bug trend charts
curl -X POST http://127.0.0.1:8000/jobs/generate-bug-charts
```

### Running Tasks Directly

For development/debugging, tasks can be run via helper scripts:

```bash
# Run from jira_server/ directory
./run_daily_job.sh        # Daily sync
./run_icebox_job.sh       # Icebox automation
./run_customer_analysis.sh
./run_data_quality.sh
./run_pushes_job.sh
./run_rca_st_job.sh
./run_compdiv_burndown.sh
./run_bug_trending_analysis.sh
```

### Database Operations

```bash
# Check database connection (Python shell from jira_server/)
cd jira_server
source venv/bin/activate
python -c "from jira_data_analysis.db_utils import get_connection_pool; pool = get_connection_pool(); print('Connected')"
```

### Development Setup

```bash
# Initial setup (creates venv and installs dependencies)
cd jira_server
./run_app.sh  # First run will set up environment

# Manual venv setup if needed
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Important Implementation Notes

### Logging System

The project uses a **centralized logging configuration** that MUST be followed:

1. **Never call `logging.basicConfig()`** in individual modules
2. **Always import logging at startup**: `main.py` calls `setup_logging()` before any other imports
3. **Use the standardized logger in all modules**:
   ```python
   from logging_utils import get_logger
   logger = get_logger(__name__)
   ```
4. **Custom log levels available**:
   - `logger.start()` - Starting a task/process
   - `logger.complete()` - Task completion (with duration)
   - `logger.success()` - Successful operation
   - `logger.processing()` - Processing data
   - `logger.connecting()` - Database/API connections

Configuration in `log_config.yaml` controls console + rotating file handlers.

### Environment Configuration

All configuration in `jira_server/.env`:

```bash
# Required variables
JIRA_URL="https://your-jira-instance.com"
JIRA_TOKEN="your_personal_access_token"
DATABASE_URL="postgresql://user:password@host:port/dbname"

# Project-specific
JIRA_PROJECTS="PROJ1,PROJ2,PROJ3"
JIRA_REPORT_DIR="./reports"
JIRA_INITIATIVE_JQL="project = COMPDIV AND type = Epic AND labels in (...)"

# See README.md for full list
```

### Database Schema Expectations

Key tables (referenced in code):
- `jira_data`: Main fact table for Jira issues
- `jira_initiatives`: Initiative-to-child mappings
- `run_log`: Tracks job execution times (used by `check_if_release_run_is_due()`)
- `bug_snapshots`: Time-series data for bug trending
- `ldap_hierarchy`: Manager/report relationships

Custom field mappings (see `data-dict.md`):
- `customfield_10301`: Epic Link
- `customfield_16301`: Parent Link
- `customfield_10102`: Sprint data
- `customfield_15600`: Pipeline stage
- `customfield_14504`: Bug origin
- `customfield_15703`: Requirement/Epic
- `customfield_15703`: Platform Version (derived for bugs)

### Jira API Best Practices

1. **Always use `get_jira_client()` from tasks.py** for consistent authentication
2. **JQL queries are environment-driven**: Defined in `.env` to allow flexible filtering
3. **Pagination**: `jira_processor.fetch_all_issues()` handles pagination automatically (50 issues/batch)
4. **Field selection**: Always specify required fields via `get_required_field_list()` to minimize API calls
5. **Timeout handling**: `JIRA_TIMEOUT_SECONDS` environment variable controls API timeouts (default 30s)

### COMPDIV Burndown System

The burndown analysis (`compdiv_burndown.py`) performs recursive BFS traversal of Jira issue links:

- **Safety limits**: `MAX_BFS_NODES = 5000` prevents runaway traversal
- **Link filtering**: `ALLOWED_LINK_TYPES` configurable (empty = all types)
- **Done detection**: Uses Jira's `statusCategory` or name hints (`DONE_NAME_HINTS`)
- **Story point estimation**: Bugs counted as 0.5 SP if no explicit points
- **Database storage**: Results stored per epic per date for historical trending
- **HTML generation**: `build_plot_html(epic_key)` creates Plotly charts from stored data

### Cron Integration

Jobs are scheduled via macOS cron (see `crontab_schedules.txt`):

```cron
# Daily sync + icebox at 9:00 AM weekdays
0 9 * * 1-5 /path/to/jira_server/run_daily_job.sh
0 9 * * 1-5 /path/to/jira_server/run_icebox_job.sh

# Daily push report at 9:15 AM
15 9 * * 1-5 /path/to/jira_server/run_pushes_job.sh
```

**Important**: Cron requires Full Disk Access on macOS (System Settings > Privacy & Security).

## Testing

Currently no automated test suite. Manual testing via:

1. Triggering endpoints with curl
2. Reviewing logs in `jira_server/logs/app.log` and `logs/access.log`
3. Checking generated reports in `jira_server/reports/`

## Common Workflows

### Adding a New Job Endpoint

1. Create task function in appropriate package (`jira_automation/` or `jira_data_analysis/`)
2. Import in `tasks.py` and create wrapper function (e.g., `run_<job>_task()`)
3. Add endpoint in `main.py` following pattern:
   ```python
   @app.post("/jobs/<job-name>", status_code=202, summary="...")
   async def trigger_<job>_job(background_tasks: BackgroundTasks):
       logger.info("<Job> endpoint triggered via API")
       logger.processing("Scheduling <job> background task")
       background_tasks.add_task(run_<job>_task)
       logger.success("<Job> scheduled")
       return {"message": "...", "status": "scheduled"}
   ```
4. Optionally create shell script in `jira_server/` (e.g., `run_<job>.sh`)

### Debugging Job Failures

1. Check `jira_server/logs/app.log` for task exceptions
2. Verify `.env` configuration (JQL queries, field names, credentials)
3. Test Jira API directly: `jira_server/get_jira_fields.py` lists all available fields
4. Check database connectivity via `db_utils.get_connection_pool()`
5. Run job script directly (e.g., `./run_daily_job.sh`) for immediate feedback

### Modifying JQL Queries

All JQL stored in `.env` as variables (e.g., `JQL_MISSING_FIXVER`). To change query logic:

1. Update `.env` variable
2. Restart FastAPI server (`./run_app.sh`)
3. No code changes needed for most reporting queries

### Working with Custom Fields

1. Run `get_jira_fields.py` to discover field IDs
2. Add mapping to `jira_processor.py` or relevant module
3. Update database schema if persisting new fields
4. Document in `data-dict.md` for reference

### Managing Completed Epics

**Automatic Closure Workflow**:

The system automatically detects and closes completed epics daily:

1. **Daily Job Execution**: The `/jobs/daily` endpoint runs `close_completed_initiatives()`
2. **Epic Detection**: Queries ALL active epics from `tbl_initiative_issue_keys`:
   ```sql
   SELECT issue_key FROM tbl_initiative_issue_keys
   WHERE (active_flag IS NULL OR active_flag = true)
   ```
3. **Status Check**: For each epic, fetches current status from Jira API
4. **Closure Decision**: If `issue.fields.status.statusCategory.name == "Done"`:
   - Sets `eff_end_date = CURRENT_DATE`
   - Sets `active_flag = false`
5. **Historical Data**: Burndown data collection continues for closed epics (shows flat zero-point lines)
6. **Dashboard Display**: Closed epics appear with bold red headers and `[COMPLETED: DATE]` badges

**Manual Reopening**:

If an epic is closed in error or needs to be reactivated:

```bash
# Connect to database
psql $DATABASE_URL

# Reopen the epic
UPDATE tbl_initiative_issue_keys
SET active_flag = NULL, eff_end_date = NULL
WHERE issue_key = 'COMPDIV-XXX';
```

**Important Considerations**:
- Epics reopened in Jira remain closed in the database until manually updated
- No data is ever deleted - all changes are fully reversible
- Closure affects BOTH COMPDIV and IRIS initiatives
- Burndown charts for closed epics continue to be generated daily

**Related Files**:
- `jira_data_analysis/initiative_children.py` - Closure logic
- `jira_server/tasks.py` - Daily job integration
- `jira_automation/generate_burndown_dashboard.py` - Visual indicators

**Verification**:

Check closure status:
```sql
-- View all closed epics
SELECT issue_key, eff_end_date, "IRIS"
FROM tbl_initiative_issue_keys
WHERE active_flag = false
ORDER BY eff_end_date DESC;

-- View active epics
SELECT issue_key, "IRIS"
FROM tbl_initiative_issue_keys
WHERE (active_flag IS NULL OR active_flag = true)
ORDER BY issue_key;
```
