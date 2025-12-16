# Jira Hygiene Automation

Comprehensive Jira automation suite for maintaining data quality and managing issue lifecycle:
1. **Icebox Process**: Two-stage process for identifying and closing stale issues
2. **RCA Subtask Creation**: Automatically creates Root Cause Analysis sub-tasks for critical bugs
3. **Data Quality Reporting**: Identifies missing required fields and sends notifications
4. **Platform Version Derivation**: Automatically populates Platform Version based on Affects Version

## Overview

This automation suite helps maintain Jira hygiene by:
- **Icebox Management**: Labeling stale issues and closing inactive ones
- **Bug Quality**: Creating RCA sub-tasks for critical production bugs
- **Data Enforcement**: Finding and reporting issues with missing required fields
- **Automated Field Population**: Deriving platform versions from affects versions
- **Manager Notifications**: Sending Teams notifications grouped by manager
- **Database Integration**: PostgreSQL connection for LDAP and reporting data

## Files Included

```
jira_hygiene/
├── README.md                        # This file
├── PACKAGE_SUMMARY.md               # Quick overview and setup guide
├── FILE_LIST.md                     # Detailed file descriptions
├── .env.sample                      # Sample environment configuration
├── requirements.txt                 # Python dependencies
├── jira_automation/
│   ├── __init__.py                 # Package marker
│   ├── jira_icebox.py              # Icebox automation logic
│   ├── create_rca_subtasks.py      # RCA subtask creation
│   ├── data_quality_report.py      # Data quality reporting
│   ├── derive_platform_version.py  # Platform version derivation
│   └── notification_utils.py       # Teams notification utilities
├── jira_data_analysis/
│   ├── __init__.py                 # Package marker
│   └── db_utils.py                 # Database connection utilities
├── logging_utils.py                 # Centralized logging utilities
├── logging_config.py                # Logging configuration setup
├── log_config.yaml                  # YAML logging configuration
└── run_icebox_job.sh               # Shell script for execution
```

## Prerequisites

### Core Requirements
- Python 3.8 or higher
- Access to a Jira instance
- Jira Personal Access Token (PAT) with permissions to:
  - Search for issues
  - Update issue fields (labels, custom fields)
  - Add comments
  - Transition issues to closed states
  - Create sub-tasks
  - Update fixVersions (if required in your workflow)

### Additional Requirements (Module-Specific)
- **Data Quality Reports**: PostgreSQL database with LDAP hierarchy table
- **Teams Notifications**: Microsoft Teams webhook URL (Power Automate or legacy)
- **Database Access**: Required for data quality reporting and manager lookups

## Installation

### 1. Set Up Python Environment

```bash
# Create a virtual environment (recommended)
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate  # On macOS/Linux
# OR
venv\Scripts\activate     # On Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
# Copy the sample environment file
cp .env.sample .env

# Edit .env with your actual values
nano .env  # or use your preferred editor
```

### Core Configuration

**Required for All Modules:**
- `JIRA_URL`: Your Jira server URL
- `JIRA_TOKEN`: Your Jira Personal Access Token
- `JIRA_PROJECTS`: Comma-separated list of project keys (e.g., "PROJ1,PROJ2,PROJ3")

**Icebox-Specific:**
- `JQL_QUERY`: JQL to find stale issues (inactive 6+ months)
- `JQL_QUERY_ICEBOX`: JQL to find icebox issues to close (30+ days with label)
- `LABEL_TO_ADD`: Label for stale issues (e.g., `compdiv-icebox`)
- `COMMENT_TO_ADD`: Comment added to stale issues
- `COMMENT_TO_ADD_ICEBOX`: Comment added when closing issues
- `JIRA_ICEBOX_FIX_VERSION`: (Optional) Specific fix version for closed issues
- `JIRA_ICEBOX_DOC_NEEDED_VALUE`: (Optional) Value for "Doc Needed" field (default: "No")

**RCA Subtask-Specific:**
- `JIRA_RCA_ORIGIN_FIELD_NAME`: Name of Origin custom field (e.g., "Origin")
- `JIRA_CREATED_DATE`: (Optional) Date filter for created issues (format: "YYYY-MM-DD")
- `COMMENT_TO_ADD_RCA_ST`: Description text for RCA sub-tasks

**Data Quality-Specific:**
- `DATABASE_URL`: PostgreSQL connection string (format: "postgresql://user:password@host:port/dbname")
- `JQL_MISSING_FIXVER`: JQL to find issues missing fix versions
- `JQL_MISSING_ORIGIN`: JQL to find issues missing origin
- `JQL_MISSING_PIPEDISC`: JQL to find issues missing pipeline discovery stage
- `JQL_MISSING_PLATVER`: JQL to find issues missing platform version
- `JQL_MISSING_SEVERITY`: JQL to find issues missing severity
- `JQL_MISSING_AFFVER`: JQL to find issues missing affects version
- `JQL_INVALID_FIXVER`: JQL to find Done issues with invalid fix versions
- `TEAMS_WEBHOOK_URL_V2`: Microsoft Teams webhook URL for notifications
- `DATA_QUALITY_EXCLUDE_PROJECTS`: (Optional) Comma-separated projects to exclude
- `DATA_QUALITY_FALLBACK_NAME`: Name for unmanaged issues notification recipient
- `DATA_QUALITY_FALLBACK_EMAIL`: Email for unmanaged issues notification recipient
- `JIRA_REPORT_DIR`: (Optional) Directory for CSV reports (default: "./reports")

### 3. Set Up Database (Required for Data Quality)

The data quality module requires a PostgreSQL database. See the **PostgreSQL Data Model** section below for complete table definitions.

### 4. Create Logs Directory

```bash
mkdir -p logs
mkdir -p reports  # For data quality CSV reports
```

## Usage

### Run Individual Modules

Each module can be run independently:

```bash
# Activate your virtual environment first
source venv/bin/activate

# 1. Icebox automation (label and close stale issues)
python -m jira_automation.jira_icebox

# 2. Create RCA sub-tasks for critical bugs
python -m jira_automation.create_rca_subtasks

# 3. Derive platform versions (usually run before data quality)
python -m jira_automation.derive_platform_version

# 4. Generate data quality report (includes platform version derivation)
python -m jira_automation.data_quality_report
```

### Run via Shell Script

The included shell script can be used for cron jobs or manual execution:

```bash
# Make the script executable
chmod +x run_icebox_job.sh

# Edit the PROJECT_DIR path in the script to match your setup
nano run_icebox_job.sh

# Run the script
./run_icebox_job.sh
```

### Schedule with Cron

To run the automation automatically (e.g., daily at 9:00 AM on weekdays):

```bash
# Edit your crontab
crontab -e

# Example cron entries:
# Icebox automation daily at 9:00 AM weekdays
0 9 * * 1-5 /path/to/jira_hygiene/run_icebox_job.sh

# RCA subtask creation daily at 9:30 AM weekdays
30 9 * * 1-5 cd /path/to/jira_hygiene && source venv/bin/activate && python -m jira_automation.create_rca_subtasks

# Data quality report daily at 10:00 AM weekdays
0 10 * * 1-5 cd /path/to/jira_hygiene && source venv/bin/activate && python -m jira_automation.data_quality_report
```

**Note on macOS:** Cron requires "Full Disk Access" permission:
1. Open System Settings > Privacy & Security > Full Disk Access
2. Add `/usr/sbin/cron` to the allowed applications

## How It Works

### Module 1: Icebox Process

#### Stage 1: Stale Issue Labeling (`update_stale_issues`)

1. Executes the JQL query defined in `JQL_QUERY`
2. For each matching issue:
   - Adds the label defined in `LABEL_TO_ADD`
   - Posts the comment defined in `COMMENT_TO_ADD`
3. Logs all actions for audit purposes

**Example JQL for Stage 1:**
```jql
project in (MYPROJECT)
AND type = Bug
AND statusCategory != Done
AND updatedDate <= endOfDay(-185)
AND labels != icebox-ignore
```

#### Stage 2: Icebox Issue Closure (`close_icebox_issues`)

1. Executes the JQL query defined in `JQL_QUERY_ICEBOX`
2. For each matching issue:
   - Closes all sub-tasks first (if any exist)
   - Finds an appropriate "Done" transition (prefers "Closed" state)
   - Sets required fields:
     - **Resolution**: Tries "Won't Do" or "Won't Fix"
     - **Fix Version**: Uses `JIRA_ICEBOX_FIX_VERSION` or finds a suitable version
     - **Doc Needed**: Sets to configured value (default: "No")
   - Transitions the issue to closed state
   - Adds the comment defined in `COMMENT_TO_ADD_ICEBOX`
3. Skips issues that cannot be closed (e.g., missing required fields)

**Example JQL for Stage 2:**
```jql
project in (MYPROJECT)
AND labels = compdiv-icebox
AND statusCategory != Done
AND type = Bug
AND updatedDate <= endOfDay(-30)
```

### Module 2: RCA Subtask Creation

1. Executes JQL query to find critical CRP bugs without "Done" status
2. For each matching issue:
   - Checks if RCA sub-task already exists (prevents duplicates)
   - Dynamically determines correct sub-task issue type ID for the project
   - Creates sub-task with summary "Root Cause Analysis(RCA)"
   - Uses description from `COMMENT_TO_ADD_RCA_ST`
3. Logs all actions including skipped issues

**JQL Logic (hardcoded with CRP origin values):**
```jql
project in (PROJECTS) AND type = Bug AND priority = Critical
AND statusCategory != Done
AND "Origin" in (BRP, CRP, 'CRP PLAT', 'CRP PREM', 'CRP STND', ICRP)
AND created >= 'JIRA_CREATED_DATE'  # Optional filter
```

### Module 3: Data Quality Reporting

1. **Platform Version Derivation**: First runs derive_platform_version module
2. **Field Checks**: Executes multiple JQL queries to find issues with missing:
   - Fix Version
   - Origin
   - Pipeline Discovery Stage
   - Platform Version
   - Severity
   - Affects Version
3. **Invalid Fix Version Check**: Finds Done issues with empty or placeholder fix versions
4. **Manager Lookup**: Enriches each issue with assignee's manager info from database
5. **CSV Generation**: Creates consolidated report in `reports/` directory
6. **Teams Notifications**:
   - Groups issues by assignee's manager
   - Sends separate notification to each manager (max 15 issues per card)
   - Includes self-assigned tickets in manager's notification
   - Sends unmanaged issues to fallback recipient
   - Uses Power Automate webhook format with @mentions

### Module 4: Platform Version Derivation

1. Executes JQL to find bugs with:
   - Empty Platform Version field
   - Non-empty Affects Version field
   - Either not in Done status OR updated in last 3 days
2. For each matching issue:
   - Examines first Affects Version
   - Applies business logic:
     - Contains 'w' or 'Viya 3' → Set to "Viya 3.5"
     - Contains '94' → Skip (SAS 9.4)
     - Contains '.' → Set to "Viya 4"
   - Updates Platform Version field in Jira
3. Logs all updates and skips

## Logging

Logs are written to two locations:
- **Console**: Real-time output during execution
- **File**: Persistent logs in `logs/app.log` (rotated at 10MB, keeps 5 backups)

Log files include:
- Detailed execution traces
- Issues processed
- Transitions attempted
- Teams notifications sent
- Database queries
- Errors and warnings

**Access logs for debugging:**
```bash
# View recent logs
tail -f logs/app.log

# Search for specific issue
grep "MYPROJECT-123" logs/app.log

# View cron execution logs (if using run_icebox_job.sh)
tail -f logs/cron_icebox.log

# Check data quality reports
ls -lh reports/
```

## Customization

### Custom Field Support

The automation dynamically discovers custom fields by name. To add support for additional fields:

1. Find your custom field name in Jira (e.g., "Epic Link", "Sprint")
2. Add logic in the relevant module similar to existing field handling
3. Use `get_custom_field_id(jira_client, "Your Field Name")` to get the field ID

### JQL Query Customization

Adjust the JQL queries to match your organization's workflow:

**Common Patterns:**
```jql
# Exclude specific labels
AND labels != icebox-ignore

# Include multiple projects
project in (PROJ1, PROJ2, PROJ3)

# Filter by issue type
AND type in (Bug, Story, Task)

# Date-based filtering
AND updatedDate <= endOfDay(-185)  # 6 months
AND createdDate >= startOfYear()    # This year only

# Status filtering
AND statusCategory != Done
AND status not in ("Waiting on Requestor", Closed)
```

### Transition Logic (Icebox)

The automation handles complex transition requirements:
- Automatically finds transitions to "Done" status category
- Prefers "Closed" status, falls back to "Accepted and Close(Q)"
- Only sets fields that are available and required for the specific transition
- Validates resolution values against allowed options
- Searches for suitable fix versions if required

### Database Schema Requirements

For data quality reporting, ensure your PostgreSQL database has:
- `tbl_ldap_hierarchy` table with email, manager_name, manager_email columns
- Proper indexes on email column for performance
- Regular updates to keep manager data current

See the **PostgreSQL Data Model** section below for complete SQL table definitions.

## PostgreSQL Data Model

The jira_hygiene automation suite requires a PostgreSQL database with the following tables. The tables support various features including LDAP hierarchy lookups, project management tracking, and execution logging.

### Required Tables

#### 1. tbl_ldap_hierarchy
Stores employee and manager relationship data from LDAP for manager lookups and notification routing.

**Used by:** `data_quality_report.py`

```sql
-- LDAP hierarchy for manager lookups
CREATE TABLE tbl_ldap_hierarchy (
    email VARCHAR(255) PRIMARY KEY,
    manager_name VARCHAR(255),
    manager_email VARCHAR(255)
);

-- Index for performance
CREATE INDEX idx_ldap_email ON tbl_ldap_hierarchy(email);
```

**Usage:** Maps Jira assignee email addresses to their managers for:
- Grouping data quality issues by manager
- Routing Teams notifications to appropriate managers
- Identifying unmanaged users (not in LDAP)

**Maintenance:** Should be refreshed regularly (e.g., weekly) from your organization's LDAP/Active Directory system.

---

#### 2. tbl_jira_project_owners
Maps Jira project keys to project owners/managers for sprint management.

**Used by:** `db_utils.py` (via `load_sprint_managers()`)

```sql
-- Jira project ownership mapping
CREATE TABLE tbl_jira_project_owners (
    project VARCHAR(50) PRIMARY KEY,
    project_owner VARCHAR(255)
);
```

**Usage:** Provides project-level ownership information for reporting and analytics.

**Example Data:**
```sql
INSERT INTO tbl_jira_project_owners (project, project_owner) VALUES
('COMPDIV', 'John Manager'),
('IRIS', 'Jane Owner'),
('PLATFORM', 'Bob Lead');
```

---

#### 3. tbl_jira_oper_epics
Maps operational epic keys to sprint teams for operational work tracking.

**Used by:** `db_utils.py` (via `load_operational_epics()`)

```sql
-- Operational epic to sprint team mapping
CREATE TABLE tbl_jira_oper_epics (
    epic VARCHAR(50) PRIMARY KEY,
    sprint_team VARCHAR(255)
);
```

**Usage:** Associates operational epics (recurring work, maintenance) with specific sprint teams.

**Example Data:**
```sql
INSERT INTO tbl_jira_oper_epics (epic, sprint_team) VALUES
('COMPDIV-100', 'Platform Team A'),
('COMPDIV-101', 'Platform Team B'),
('IRIS-50', 'IRIS Core Team');
```

---

#### 4. tbl_initiative_issue_keys
Stores initiative/epic issue keys for tracking high-level work streams.

**Used by:** `db_utils.py` (via `fetch_initiative_keys()`)

```sql
-- Initiative and epic tracking
CREATE TABLE tbl_initiative_issue_keys (
    issue_key VARCHAR(50) PRIMARY KEY
);
```

**Usage:** Maintains a list of strategic initiative and epic keys for:
- Release planning
- Portfolio management
- Initiative-level reporting

**Example Data:**
```sql
INSERT INTO tbl_initiative_issue_keys (issue_key) VALUES
('COMPDIV-200'),
('COMPDIV-201'),
('IRIS-100'),
('IRIS-101');
```

---

#### 5. tbl_run_log
Tracks execution history of automation jobs for auditing and scheduling logic.

**Used by:** `db_utils.py` (via `update_run_log()` and `release_run_check()`)

```sql
-- Execution log for automation runs
CREATE TABLE tbl_run_log (
    id SERIAL PRIMARY KEY,
    "execOrigin" VARCHAR(50),
    "startDTTM" TIMESTAMP,
    "endDTTM" TIMESTAMP,
    "sprint" VARCHAR(50),
    "runType" VARCHAR(50)
);

-- Indexes for performance
CREATE INDEX idx_run_log_runtype ON tbl_run_log("runType");
CREATE INDEX idx_run_log_enddttm ON tbl_run_log("endDTTM");
```

**Usage:**
- Logs each execution of automation jobs (daily, release, icebox, etc.)
- Determines if release analysis should run based on last execution date
- Provides audit trail for all automation activities

**Run Types:**
- `DAILY` - Daily data synchronization runs
- `RELEASE` - Release analysis runs
- `ICEBOX` - Icebox automation runs
- Custom run types as needed

**Example Data:**
```sql
-- Example log entries
INSERT INTO tbl_run_log ("execOrigin", "startDTTM", "endDTTM", "sprint", "runType") VALUES
('python', '2025-01-15 09:00:00', '2025-01-15 09:15:00', 'daily', 'DAILY'),
('python', '2025-01-15 09:30:00', '2025-01-15 09:45:00', 'icebox', 'ICEBOX'),
('python', '2025-01-20 10:00:00', '2025-01-20 11:30:00', 'release', 'RELEASE');
```

---

#### 6. tbl_jira_releases
Stores release dates for determining when release analysis should trigger.

**Used by:** `db_utils.py` (via `release_run_check()`)

```sql
-- Release date tracking
CREATE TABLE tbl_jira_releases (
    release_date DATE PRIMARY KEY,
    release_name VARCHAR(255)
);

-- Index for performance
CREATE INDEX idx_release_date ON tbl_jira_releases(release_date);
```

**Usage:**
- Defines target release dates for the organization
- Triggers release analysis when most recent release date has passed
- Prevents duplicate release runs for the same release period

**Example Data:**
```sql
INSERT INTO tbl_jira_releases (release_date, release_name) VALUES
('2025-01-31', 'Q1 2025 Release'),
('2025-04-30', 'Q2 2025 Release'),
('2025-07-31', 'Q3 2025 Release'),
('2025-10-31', 'Q4 2025 Release');
```

### Database Setup Script

Here's a complete script to set up all required tables:

```sql
-- Create all required tables for jira_hygiene automation

-- 1. LDAP hierarchy for manager lookups
CREATE TABLE IF NOT EXISTS tbl_ldap_hierarchy (
    email VARCHAR(255) PRIMARY KEY,
    manager_name VARCHAR(255),
    manager_email VARCHAR(255)
);
CREATE INDEX IF NOT EXISTS idx_ldap_email ON tbl_ldap_hierarchy(email);

-- 2. Project ownership mapping
CREATE TABLE IF NOT EXISTS tbl_jira_project_owners (
    project VARCHAR(50) PRIMARY KEY,
    project_owner VARCHAR(255)
);

-- 3. Operational epic to team mapping
CREATE TABLE IF NOT EXISTS tbl_jira_oper_epics (
    epic VARCHAR(50) PRIMARY KEY,
    sprint_team VARCHAR(255)
);

-- 4. Initiative tracking
CREATE TABLE IF NOT EXISTS tbl_initiative_issue_keys (
    issue_key VARCHAR(50) PRIMARY KEY
);

-- 5. Execution log
CREATE TABLE IF NOT EXISTS tbl_run_log (
    id SERIAL PRIMARY KEY,
    "execOrigin" VARCHAR(50),
    "startDTTM" TIMESTAMP,
    "endDTTM" TIMESTAMP,
    "sprint" VARCHAR(50),
    "runType" VARCHAR(50)
);
CREATE INDEX IF NOT EXISTS idx_run_log_runtype ON tbl_run_log("runType");
CREATE INDEX IF NOT EXISTS idx_run_log_enddttm ON tbl_run_log("endDTTM");

-- 6. Release date tracking
CREATE TABLE IF NOT EXISTS tbl_jira_releases (
    release_date DATE PRIMARY KEY,
    release_name VARCHAR(255)
);
CREATE INDEX IF NOT EXISTS idx_release_date ON tbl_jira_releases(release_date);
```

### Database Connection

All modules use the centralized database connection pool from `db_utils.py`:

```python
from jira_data_analysis import db_utils

# Get the connection pool (initialized at module load)
db_pool = db_utils.get_connection_pool()

# Use a connection
conn = db_pool.getconn()
try:
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM tbl_ldap_hierarchy LIMIT 1")
        # ... your query logic ...
finally:
    db_pool.putconn(conn)
```

**Connection Pool Configuration:**
- Min connections: 1
- Max connections: 20
- Connection string: Set via `DATABASE_URL` environment variable

**Example DATABASE_URL:**
```
postgresql://username:password@hostname:5432/database_name
```

### Table Relationships

```
┌─────────────────────────┐
│  tbl_ldap_hierarchy     │
│  (Manager Lookups)      │
└─────────────────────────┘
          ↓
    Used by data_quality_report
    to route notifications

┌─────────────────────────┐
│ tbl_jira_project_owners │
│ (Project Management)    │
└─────────────────────────┘

┌─────────────────────────┐
│  tbl_jira_oper_epics    │
│  (Team Assignments)     │
└─────────────────────────┘

┌─────────────────────────┐
│tbl_initiative_issue_keys│
│  (Strategic Tracking)   │
└─────────────────────────┘

┌─────────────────────────┐        ┌─────────────────────────┐
│    tbl_run_log          │◄───────┤  tbl_jira_releases      │
│  (Execution History)    │        │  (Release Schedule)     │
└─────────────────────────┘        └─────────────────────────┘
          ↓
    release_run_check() uses both tables
    to determine if release analysis should run
```

### Maintenance Tasks

**Daily:**
- No daily maintenance required

**Weekly:**
- Refresh `tbl_ldap_hierarchy` from LDAP/Active Directory
- Review `tbl_run_log` for any failed executions

**Monthly:**
- Add upcoming release dates to `tbl_jira_releases`
- Archive old `tbl_run_log` entries (optional, for performance)

**As Needed:**
- Update `tbl_jira_project_owners` when project ownership changes
- Update `tbl_jira_oper_epics` when operational epics are created
- Update `tbl_initiative_issue_keys` for new strategic initiatives

## Troubleshooting

### Issue: "Could not find a valid transition to 'Closed'"

**Solution:** Check your Jira workflow configuration:
```bash
# The issue may have no available transitions to Done status
# Verify the issue's current status allows transitions to Closed
```

### Issue: "fixVersions is required but no suitable version found"

**Solutions:**
1. Set `JIRA_ICEBOX_FIX_VERSION` to an existing fix version in your project
2. Create a fix version named "Not Planned" or "Unscheduled" in your Jira project
3. Modify the version search keywords in `_find_and_apply_done_transition()`

### Issue: "Could not find custom field named 'Origin'"

**Solution:** Custom field names are case-sensitive:
1. Go to Jira > Settings > Issues > Custom Fields
2. Find the exact name of the field (including capitalization)
3. Update the field name in your .env file to match exactly

### Issue: "Database pool is not available"

**Solutions:**
1. Verify DATABASE_URL is set correctly in .env
2. Check that PostgreSQL is running and accessible
3. Test connection: `psql $DATABASE_URL -c "SELECT 1"`
4. Ensure firewall allows connection to database host

### Issue: "Teams notification failed"

**Solutions:**
1. Verify TEAMS_WEBHOOK_URL_V2 is valid and not expired
2. Test webhook manually with curl:
   ```bash
   curl -X POST -H 'Content-Type: application/json' \
     -d '{"text":"Test"}' \
     $TEAMS_WEBHOOK_URL_V2
   ```
3. Check Power Automate flow is active (for V2 webhooks)
4. Ensure payload size is under 28KB limit (handled via batching)

### Issue: Logging not working

**Solution:** Ensure the logs directory exists:
```bash
mkdir -p logs
chmod 755 logs
```

### Issue: Authentication failures

**Solutions:**
1. Verify your Jira Personal Access Token is valid and not expired
2. Check token permissions include:
   - Browse projects
   - Edit issues
   - Add comments
   - Transition issues
   - Create sub-tasks
3. Test connection manually:
   ```python
   from jira import JIRA
   jira = JIRA(server='YOUR_JIRA_URL', token_auth='YOUR_TOKEN')
   print(jira.server_info())
   ```

### Issue: RCA sub-tasks not being created

**Solutions:**
1. Verify `JIRA_RCA_ORIGIN_FIELD_NAME` matches exact field name in Jira
2. Check that sub-task issue type exists in your project
3. Ensure issues match the JQL criteria (Critical, CRP origin, not Done)
4. Check logs for "Found 0 critical CRP bugs" - may need to adjust date filter

### Issue: Data quality report empty

**Solutions:**
1. Verify JQL queries in .env are returning results (test in Jira search)
2. Check that LDAP hierarchy table has data
3. Ensure DATA_QUALITY_EXCLUDE_PROJECTS isn't excluding too many projects
4. Look for "No issues found matching the criteria" in logs

## Security Considerations

**Protect Your Credentials:**
- Never commit `.env` files to version control
- Restrict file permissions: `chmod 600 .env`
- Rotate Jira tokens periodically (quarterly recommended)
- Use service accounts for automation (not personal accounts)
- Store DATABASE_URL securely (consider using secrets manager)
- Protect Teams webhook URLs (they provide direct channel access)

**Audit Trail:**
- All actions are logged with timestamps
- Comments are posted to issues explaining automated actions
- Changes are reversible (issues can be reopened, labels removed)
- CSV reports provide audit history
- Teams notifications create permanent message trail

**Database Security:**
- Use read-only database credentials if possible (for data quality module)
- Ensure database connection is encrypted (use SSL)
- Limit database user permissions to required tables only
- Regularly audit database access logs

## Support and Maintenance

### Monitoring

Check logs regularly for:
- Failed transitions
- Authentication errors
- Issues skipped due to missing fields
- Database connection issues
- Teams notification failures

### Testing

Before deploying to production:
1. Test with a small subset of issues
2. Verify JQL queries return expected results
3. Check that transitions work in your workflow
4. Review comments and labels applied
5. Verify Teams notifications reach correct recipients
6. Test database connectivity and query performance

### Rollback

If needed, you can manually revert automated actions:
```jql
# Find all issues processed by automation
project = MYPROJECT
AND comment ~ "THIS IS AN AUTOMATED MESSAGE"
AND labels = compdiv-icebox

# Then bulk remove labels or reopen issues as needed
```

For RCA sub-tasks:
```jql
# Find and delete RCA sub-tasks if needed
summary ~ "Root Cause Analysis(RCA)"
AND type = Sub-task
AND created >= -7d
```

### Performance Optimization

For large Jira instances:
- Limit JQL queries with date ranges
- Use maxResults parameter to batch processing
- Schedule jobs during off-peak hours
- Monitor API rate limits
- Consider indexing LDAP hierarchy table

## Example Workflows

### Workflow 1: Daily Hygiene Automation

**Week 1-26:** Issues are worked on normally

**Week 27 (6 months of inactivity):**
- Icebox automation runs: `update_stale_issues()`
- Issue gets `compdiv-icebox` label
- Comment posted: "Issue marked as stale..."
- Stakeholders can remove label if still relevant

**Week 31 (30+ days with icebox label):**
- Icebox automation runs: `close_icebox_issues()`
- Issue is transitioned to Closed
- Resolution set to "Won't Do"
- Comment posted: "Issue closed due to inactivity..."
- Fix Version set to "Not Planned"

**Result:** Clean backlog with clear audit trail

### Workflow 2: Bug Quality Enforcement

**Day 1:** Critical bug created (Priority=Critical, Origin=CRP)

**Day 2 (9:30 AM cron):**
- RCA automation runs
- Detects critical CRP bug without RCA sub-task
- Creates sub-task "Root Cause Analysis(RCA)"
- Assigns to same assignee as parent
- Logs action for audit

**Day 3 (10:00 AM cron):**
- Data quality report runs
- Platform version derivation updates Viya fields
- Detects bug missing "Pipeline Discovery Stage"
- Generates CSV report with issue details
- Sends Teams notification to bug assignee's manager
- Manager receives @mention in Teams

**Result:** Enforced process compliance and manager visibility

## License

This automation is provided as-is for internal use. Modify as needed for your organization's requirements.

## Contact

For questions or issues, contact your Jira administrator or the automation maintainer.
