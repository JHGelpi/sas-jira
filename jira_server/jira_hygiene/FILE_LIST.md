# Jira Hygiene Package - File Listing

This document describes all files included in the Jira Hygiene automation package.

## Package Structure

```
jira_hygiene/
├── README.md                        # Comprehensive setup and usage guide
├── FILE_LIST.md                     # This file - describes all included files
├── PACKAGE_SUMMARY.md               # Quick overview and setup guide
├── .env.sample                      # Sample environment variables with descriptions
├── requirements.txt                 # Python dependencies
│
├── jira_automation/
│   ├── __init__.py                  # Python package marker
│   ├── jira_icebox.py              # Icebox automation logic (~330 lines)
│   ├── create_rca_subtasks.py      # RCA subtask creation (~177 lines)
│   ├── data_quality_report.py      # Data quality reporting (~435 lines)
│   ├── derive_platform_version.py  # Platform version derivation (~141 lines)
│   └── notification_utils.py       # Teams notification utilities (~111 lines)
│
├── jira_data_analysis/
│   ├── __init__.py                  # Python package marker
│   └── db_utils.py                 # Database utilities (~166 lines)
│
├── logging_utils.py                 # Centralized logging utilities with emoji support
├── logging_config.py                # Logging configuration loader
├── log_config.yaml                  # YAML logging configuration
├── run_icebox_job.sh               # Shell script for icebox automation
├── run_rca_st_job.sh               # Shell script for RCA subtask creation
├── run_data_quality.sh             # Shell script for data quality report
├── run_derive_data.sh              # Shell script for platform version derivation
└── run_server.sh                   # Shell script for FastAPI server
```

## File Descriptions

### Configuration Files

#### `.env.sample`
- **Purpose**: Template for environment variables
- **Usage**: Copy to `.env` and fill in actual values
- **Contains**:
  - Jira connection settings (URL, token, projects)
  - Icebox JQL queries, labels, and comments
  - RCA subtask configuration (origin field, date filter, description)
  - Data quality JQL queries and Teams webhook
  - Database connection string
  - Optional customization parameters

#### `requirements.txt`
- **Purpose**: Python package dependencies
- **Usage**: `pip install -r requirements.txt`
- **Dependencies**:
  - `jira` - Jira Python API client
  - `python-dotenv` - Environment variable management
  - `pyyaml` - YAML configuration parsing
  - `psycopg2-binary` - PostgreSQL database adapter
  - `requests` - HTTP requests for Teams notifications
  - `fastapi` - Web framework (for API server mode)
  - `uvicorn[standard]` - ASGI server
  - `python-dateutil` - Date parsing utility

#### `log_config.yaml`
- **Purpose**: Logging configuration
- **Features**:
  - Console output for real-time monitoring
  - Rotating file handler (10MB files, keeps 5 backups)
  - Separate access log handler for web requests (if using API server)
  - Configurable log levels per module

### Core Python Modules

#### `jira_automation/jira_icebox.py`
- **Purpose**: Main icebox automation logic
- **Size**: ~330 lines
- **Functions**:
  - `setup_jira_client()` - Authenticates to Jira
  - `update_stale_issues()` - Stage 1: Labels and comments on stale issues
  - `close_icebox_issues()` - Stage 2: Closes issues with icebox label
  - `_find_and_apply_done_transition()` - Handles complex transition logic
  - `_get_custom_field_id()` - Dynamic custom field discovery
- **Features**:
  - Closes sub-tasks before parent issues
  - Handles required fields during transitions
  - Validates resolution values
  - Searches for appropriate fix versions
  - Sets "Doc Needed" field if required
  - Comprehensive error handling and logging

#### `jira_automation/create_rca_subtasks.py`
- **Purpose**: Automatically creates RCA sub-tasks for critical bugs
- **Size**: ~177 lines
- **Functions**:
  - `connect_to_jira()` - Jira client initialization
  - `get_custom_field_id()` - Finds custom field IDs by name
  - `get_subtask_issue_type_id()` - Dynamically determines sub-task type per project
  - `create_rca_subtasks()` - Main automation logic
  - `main()` - Entry point with environment setup
- **Features**:
  - Finds critical CRP bugs (BRP, CRP, CRP PLAT, CRP PREM, CRP STND, ICRP)
  - Prevents duplicate sub-task creation
  - Caches sub-task type IDs per project for performance
  - Supports optional date filtering
  - Logs all actions for audit

#### `jira_automation/data_quality_report.py`
- **Purpose**: Data quality reporting and enforcement
- **Size**: ~435 lines
- **Functions**:
  - `connect_to_jira()` - Jira client initialization
  - `get_custom_field_ids()` - Finds multiple custom field IDs
  - `get_ldap_data_from_db()` - Fetches manager hierarchy from PostgreSQL
  - `get_project_exclusion_clause()` - Builds JQL exclusion for specific projects
  - `fetch_issues_for_report()` - Executes JQL and enriches results with manager info
  - `check_invalid_fix_versions_for_done_issues()` - Finds Done issues with invalid versions
  - `write_consolidated_report()` - Generates CSV and sends Teams notifications
  - `main()` - Orchestrates all reports
- **Features**:
  - Checks 7 different data quality rules
  - Enriches issues with manager information from LDAP database
  - Generates timestamped CSV reports
  - Groups issues by manager for accountability
  - Sends batched Teams notifications (max 15 issues per card)
  - Handles self-assigned manager tickets
  - Supports fallback recipient for unmanaged issues
  - Project exclusion capability

#### `jira_automation/derive_platform_version.py`
- **Purpose**: Platform version derivation automation
- **Size**: ~141 lines
- **Functions**:
  - `connect_to_jira()` - Jira client initialization
  - `get_custom_field_id()` - Finds Platform Version custom field
  - `derive_and_update_platform_version()` - Main derivation logic
  - `main()` - Entry point with environment setup
- **Features**:
  - Finds bugs with empty Platform Version but populated Affects Version
  - Applies business logic rules:
    - Contains 'w' or 'Viya 3' → "Viya 3.5"
    - Contains '94' → Skip (SAS 9.4)
    - Contains '.' → "Viya 4"
  - Updates issues in Jira
  - Works on non-Done issues OR recently updated Done issues (last 3 days)
  - Logs all updates and skips

#### `jira_automation/notification_utils.py`
- **Purpose**: Teams notification utilities
- **Size**: ~111 lines
- **Functions**:
  - `send_teams_notification()` - Sends Adaptive Card to Microsoft Teams
- **Features**:
  - Supports both Power Automate and legacy Office 365 Connector webhooks
  - Adaptive Card format with FactSets
  - @mention support with proper entities
  - Full-width cards for better visibility
  - Error handling and detailed logging
  - Configurable via TEAMS_WEBHOOK_URL_V2 environment variable

#### `jira_data_analysis/db_utils.py`
- **Purpose**: Database connection and utilities
- **Size**: ~166 lines
- **Functions**:
  - `initialize_connection_pool()` - Creates psycopg2 connection pool
  - `get_connection_pool()` - Returns initialized pool
  - `load_sprint_managers()` - Loads project owners from database
  - `load_operational_epics()` - Loads operational epic mappings
  - `fetch_initiative_keys()` - Fetches initiative issue keys
  - `update_run_log()` - Logs execution details
  - `release_run_check()` - Checks if release run is due
- **Features**:
  - Connection pooling (1-20 connections)
  - Automatic initialization on module import
  - Environment-driven configuration
  - Error handling with sys.exit on fatal errors
  - Support for multiple database operations

### Shared Utilities

#### `logging_utils.py`
- **Purpose**: Standardized logging wrapper
- **Size**: ~239 lines
- **Features**:
  - Custom log methods: `.success()`, `.start()`, `.complete()`, `.connecting()`, `.searching()`, `.processing()`, `.skip()`, `.database()`
  - Emoji support (configurable via `LOG_USE_EMOJI`)
  - ANSI color support (configurable via `LOG_USE_COLORS`)
  - Section headers for better log readability
- **Classes**:
  - `StandardizedLogger` - Main logger wrapper
  - `Colors` - ANSI color code constants
  - `Emoji` - Standardized emoji set

#### `logging_config.py`
- **Purpose**: Centralized logging initialization
- **Size**: ~111 lines
- **Function**: `setup_logging()` - Loads log_config.yaml and configures Python logging
- **Features**:
  - Creates logs directory if missing
  - Falls back to basic config if YAML loading fails
  - Prevents duplicate logging configuration
  - Sets up both console and file handlers

### Scripts

#### `run_icebox_job.sh`
- **Purpose**: Shell script to execute icebox automation
- **Usage**: Can be run manually or via cron
- **Features**:
  - Creates log directory if missing
  - Logs execution start/end timestamps
  - Redirects output to `logs/cron_icebox.log`
  - Uses curl to trigger `/jobs/jiraicebox` API endpoint
- **Configuration**: Edit `PROJECT_DIR` variable to match your installation path

#### `run_rca_st_job.sh`
- **Purpose**: Shell script to execute RCA subtask creation
- **Usage**: Can be run manually or via cron
- **Features**:
  - Creates log directory if missing
  - Logs execution start/end timestamps
  - Redirects output to `logs/cron_pushes.log`
  - Uses curl to trigger `/jobs/create-rca-subtasks` API endpoint
- **Configuration**: Edit `PROJECT_DIR` variable to match your installation path

#### `run_data_quality.sh`
- **Purpose**: Shell script to execute data quality report generation
- **Usage**: Can be run manually or via cron
- **Features**:
  - Creates log directory if missing
  - Logs execution start/end timestamps
  - Redirects output to `logs/cron_pushes.log`
  - Uses curl to trigger `/jobs/data-quality-report` API endpoint
- **Configuration**: Edit `PROJECT_DIR` variable to match your installation path

#### `run_derive_data.sh`
- **Purpose**: Shell script to execute platform version derivation
- **Usage**: Can be run manually or via cron
- **Features**:
  - Creates log directory if missing
  - Logs execution start/end timestamps
  - Redirects output to `logs/cron_pushes.log`
  - Uses curl to trigger `/jobs/derive-platform-version` API endpoint
- **Configuration**: Edit `PROJECT_DIR` variable to match your installation path

#### `run_server.sh`
- **Purpose**: Shell script to start the FastAPI server
- **Usage**: Run before using any of the curl-based shell scripts
- **Features**:
  - Activates virtual environment
  - Installs dependencies from requirements.txt
  - Starts uvicorn server on port 8000
  - Required for API endpoint mode (all run_*.sh scripts depend on this)
- **Note**: Server must be running for the other shell scripts to work

### Documentation

#### `README.md`
- **Purpose**: Complete setup and usage guide
- **Sections**:
  - Overview of all four modules
  - Installation instructions (Python, database, configuration)
  - Configuration guide for all modules
  - Usage examples (manual, script, cron)
  - How it works (detailed workflow for each module)
  - Logging information
  - Customization options
  - Troubleshooting guide (module-specific issues)
  - Security considerations (credentials, database, Teams)
  - Example workflows

#### `PACKAGE_SUMMARY.md`
- **Purpose**: Quick overview and setup guide
- **Sections**:
  - Package contents with file tree
  - What each module does
  - Quick start instructions
  - Core configuration variables
  - Module usage examples
  - Expected output samples
  - Common issues and solutions
  - Integration options
  - Monitoring and best practices

#### `FILE_LIST.md`
- **Purpose**: This file - describes all package contents
- **Sections**:
  - Package structure
  - File descriptions
  - Environment variable reference
  - Dependencies and requirements

## Environment Variables Reference

### Core Variables (All Modules)

| Variable | Purpose | Example |
|----------|---------|---------|
| `JIRA_URL` | Jira server URL | `https://jira.company.com/` |
| `JIRA_TOKEN` | Personal Access Token | `NTAwMzk3MD...` |
| `JIRA_PROJECTS` | Comma-separated project keys | `PROJ1,PROJ2,PROJ3` |

### Icebox Module Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `JQL_QUERY` | Find stale issues | `project = MYPROJ AND updatedDate <= endOfDay(-185)` |
| `JQL_QUERY_ICEBOX` | Find icebox issues to close | `labels = icebox AND updatedDate <= endOfDay(-30)` |
| `LABEL_TO_ADD` | Label for stale issues | `compdiv-icebox` |
| `COMMENT_TO_ADD` | Comment for stale issues | `This issue has been marked as stale...` |
| `COMMENT_TO_ADD_ICEBOX` | Comment when closing | `This issue has been closed...` |
| `JIRA_ICEBOX_FIX_VERSION` | Fix version for closed issues | `Not Planned` |
| `JIRA_ICEBOX_DOC_NEEDED_VALUE` | Doc Needed field value | `No` |

### RCA Subtask Module Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `JIRA_RCA_ORIGIN_FIELD_NAME` | Name of Origin custom field | `Origin` |
| `JIRA_CREATED_DATE` | Optional date filter | `2024-01-01` |
| `COMMENT_TO_ADD_RCA_ST` | RCA sub-task description | `Please complete root cause analysis...` |

### Data Quality Module Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` |
| `JQL_MISSING_FIXVER` | Find missing fix versions | `project = X AND fixVersion is EMPTY` |
| `JQL_MISSING_ORIGIN` | Find missing origin | `project = X AND Origin is EMPTY` |
| `JQL_MISSING_PIPEDISC` | Find missing pipeline discovery | `project = X AND "Pipeline Discovery Stage" is EMPTY` |
| `JQL_MISSING_PLATVER` | Find missing platform version | `project = X AND "Platform Version" is EMPTY` |
| `JQL_MISSING_SEVERITY` | Find missing severity | `project = X AND Severity is EMPTY` |
| `JQL_MISSING_AFFVER` | Find missing affects version | `project = X AND affectedVersion is EMPTY` |
| `JQL_INVALID_FIXVER` | Find Done issues with invalid versions | `statusCategory = Done AND fixVersion in (Now, Next, Future)` |
| `TEAMS_WEBHOOK_URL_V2` | Microsoft Teams webhook | `https://example.powerplatform.com/...` |
| `DATA_QUALITY_EXCLUDE_PROJECTS` | Projects to exclude | `SIGNOFF,TESTPROJ` |
| `DATA_QUALITY_FALLBACK_NAME` | Fallback recipient name | `Admin Team` |
| `DATA_QUALITY_FALLBACK_EMAIL` | Fallback recipient email | `admin@example.com` |
| `JIRA_REPORT_DIR` | CSV report directory | `./reports` |

### Optional Variables

| Variable | Purpose | Default | Example |
|----------|---------|---------|---------|
| `LOG_USE_EMOJI` | Enable emoji in logs | `true` | `true`/`false` |
| `LOG_USE_COLORS` | Enable ANSI colors | `false` | `true`/`false` |

## Dependencies and Requirements

### System Requirements
- Python 3.8 or higher
- Bash shell (for run_icebox_job.sh)
- PostgreSQL database (for data quality module)
- curl (for shell script API mode)

### Python Package Dependencies
- **jira** (3.0+) - Official Jira Python library
- **python-dotenv** (0.19+) - Load environment variables from .env
- **PyYAML** (6.0+) - Parse YAML configuration files
- **psycopg2-binary** (2.9+) - PostgreSQL database adapter
- **requests** (2.28+) - HTTP library for Teams notifications
- **fastapi** (0.100+) - Web framework (optional, for API server)
- **uvicorn[standard]** (0.23+) - ASGI server (optional, for API server)
- **python-dateutil** (2.8+) - Date parsing utility

### Jira Permissions Required
- Browse Projects
- Edit Issues (labels, comments, custom fields)
- Transition Issues
- Create Sub-tasks
- Edit Fix Versions (if fixVersions field is required in workflow)
- View custom fields

### Database Requirements
- PostgreSQL 10+ (for data quality module)
- Table: `tbl_ldap_hierarchy` with columns:
  - `email` VARCHAR(255) PRIMARY KEY
  - `manager_name` VARCHAR(255)
  - `manager_email` VARCHAR(255)
- Recommend index on `email` column for performance

### Teams Integration Requirements
- Microsoft Teams workspace
- Power Automate flow with HTTP trigger OR legacy Office 365 Connector
- Webhook URL with POST permissions
- Webhook must accept Adaptive Card format

## Usage Modes

### Standalone Execution
Run directly as a Python script for each module:
```bash
python -m jira_automation.jira_icebox
python -m jira_automation.create_rca_subtasks
python -m jira_automation.derive_platform_version
python -m jira_automation.data_quality_report
```

### Shell Script Execution
Run via the included shell script:
```bash
./run_icebox_job.sh  # Icebox module only
```

### Cron Job
Schedule automated runs:
```cron
# Icebox daily at 9:00 AM on weekdays
0 9 * * 1-5 /path/to/jira_hygiene/run_icebox_job.sh

# RCA daily at 9:30 AM on weekdays
30 9 * * 1-5 cd /path/to/jira_hygiene && source venv/bin/activate && python -m jira_automation.create_rca_subtasks

# Data quality daily at 10:00 AM on weekdays
0 10 * * 1-5 cd /path/to/jira_hygiene && source venv/bin/activate && python -m jira_automation.data_quality_report
```

### API Integration
The shell script uses curl to trigger an API endpoint. To use standalone mode:
1. Modify `run_icebox_job.sh` to call Python directly instead of curl
2. Replace line 21 with:
   ```bash
   cd "$PROJECT_DIR" && source venv/bin/activate && python -m jira_automation.jira_icebox >> "$LOG_FILE" 2>&1
   ```

## Logs and Output

### Log Files Created
- `logs/app.log` - Main application log (rotating, 10MB max, 5 backups)
- `logs/cron_icebox.log` - Cron execution log (if using shell script)
- `logs/access.log` - API access log (if using FastAPI server)

### Report Files Created
- `reports/data_quality_report_YYYY-MM-DD.csv` - Daily data quality reports

### Log Rotation
- **Max File Size**: 10 MB per log file
- **Backup Count**: 5 old log files kept
- **Total Max Size**: ~60 MB per log stream (current + 5 backups)

### Log Contents
- Timestamps for all operations
- Issues processed (key + summary)
- Labels added, sub-tasks created, fields updated
- Comments posted
- Transitions attempted
- Teams notifications sent
- Database queries and connections
- Errors and warnings
- Success/skip counts

## Testing

Before deploying to production, test with a small subset:

1. **Test JQL queries** in Jira's issue search to verify results
2. **Create test issues** that match your criteria
3. **Test database connection**: `psql $DATABASE_URL -c "SELECT COUNT(*) FROM tbl_ldap_hierarchy"`
4. **Test Teams webhook**: Send a test notification manually
5. **Run manually** first: `python -m jira_automation.[module_name]`
6. **Review logs** to ensure expected behavior
7. **Verify Jira** to confirm labels, comments, sub-tasks, and transitions
8. **Check Teams** for notification delivery and formatting

## Maintenance

### Regular Tasks
- Monitor logs for errors or warnings
- Rotate Jira tokens periodically (quarterly recommended)
- Review and update JQL queries as workflow changes
- Test transitions after Jira workflow updates
- Update LDAP hierarchy table with current manager data
- Verify Teams webhook remains active
- Check database connection performance

### Version Control
- Keep `.env` out of version control (add to .gitignore)
- Version control all other files
- Document any customizations made
- Track changes to JQL queries and business logic

## Support

For issues or questions:
1. Check the troubleshooting section in README.md
2. Review logs in `logs/app.log` for detailed error messages
3. Verify Jira permissions and workflow configuration
4. Test database connectivity and LDAP data
5. Check Teams webhook status
6. Contact your Jira administrator for workflow-specific issues

---

**Package Version**: 2.0
**Last Updated**: 2025-12-16
**Python Version**: 3.8+
**Tested with**: Jira Cloud and Jira Data Center
