# Jira Hygiene Automation - Package Summary

## ✅ Package Complete

Your Jira hygiene automation suite has been packaged into a standalone folder ready for sharing!

**Location**: `/Users/wegelpi/github_repos/sas-jira/jira_server/jira_hygiene/`

## 📦 What's Included

### Complete Package Contents:

```
jira_hygiene/
├── README.md                    ⭐ START HERE - Complete setup guide
├── PACKAGE_SUMMARY.md           📋 This file - Quick overview
├── FILE_LIST.md                 📄 Detailed file descriptions
├── .env.sample                  🔧 Sample environment variables
├── requirements.txt             📦 Python dependencies
├── run_icebox_job.sh           🚀 Shell script for icebox automation
├── run_rca_st_job.sh           🚀 Shell script for RCA subtask creation
├── run_data_quality.sh         🚀 Shell script for data quality report
├── run_derive_data.sh          🚀 Shell script for platform version derivation
├── run_server.sh               🚀 Shell script for FastAPI server
├── log_config.yaml             ⚙️  Logging configuration
├── logging_config.py           🔍 Logging setup module
├── logging_utils.py            📝 Logging utilities
├── jira_automation/
│   ├── __init__.py             🔹 Package marker
│   ├── jira_icebox.py          💎 Icebox automation logic
│   ├── create_rca_subtasks.py  🔧 RCA subtask creation
│   ├── data_quality_report.py  📊 Data quality reporting
│   ├── derive_platform_version.py 🏷️  Platform version derivation
│   └── notification_utils.py   📧 Teams notification utilities
└── jira_data_analysis/
    ├── __init__.py             🔹 Package marker
    └── db_utils.py             🗄️  Database connection utilities
```

## 🎯 What This Package Does

**Comprehensive Jira Hygiene Automation Suite:**

### 1. Icebox Process (Two-Stage Issue Lifecycle)
   - **Stage 1 - Labeling** (Day 0):
     - Finds issues inactive for 6+ months
     - Adds `compdiv-icebox` label
     - Posts notification comment
     - Allows 30 days for response
   - **Stage 2 - Closure** (Day 30):
     - Closes issues with icebox label inactive 30+ days
     - Handles sub-tasks first
     - Sets resolution, fix version, etc.
     - Posts final comment

### 2. RCA Subtask Creation
   - Automatically creates Root Cause Analysis (RCA) sub-tasks for critical CRP bugs
   - Prevents duplicate sub-task creation
   - Supports multiple projects with dynamic sub-task type detection
   - Configurable via JQL queries and custom field mappings

### 3. Data Quality Reporting
   - Identifies issues with missing required fields:
     - Fix Version, Origin, Pipeline Discovery Stage
     - Platform Version, Severity, Affects Version
   - Generates consolidated CSV reports
   - Sends granular Teams notifications to managers
   - Groups issues by assignee's manager for accountability
   - Handles unmanaged issues with fallback notification

### 4. Platform Version Derivation
   - Automatically populates Platform Version field based on Affects Version
   - Uses business logic rules to determine Viya 3.5 vs Viya 4
   - Updates issues that meet specific criteria
   - Runs as prerequisite for data quality reporting

## 🚀 Quick Start

### 1. Extract Package
```bash
# Copy the jira_hygiene folder to your desired location
cp -r jira_hygiene /path/to/destination/
cd /path/to/destination/jira_hygiene
```

### 2. Install Dependencies
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install packages
pip install -r requirements.txt
```

### 3. Configure Database (Required for Data Quality Reports)
```bash
# Set DATABASE_URL in .env for PostgreSQL connection
DATABASE_URL="postgresql://user:password@host:port/dbname"
```

### 4. Configure
```bash
# Copy sample environment file
cp .env.sample .env

# Edit with your Jira credentials and settings
nano .env  # or use your preferred editor
```

**Core Required Variables:**
- `JIRA_URL` - Your Jira server URL
- `JIRA_TOKEN` - Your Jira Personal Access Token (PAT)
- `JIRA_PROJECTS` - Comma-separated list of project keys

**Icebox-Specific:**
- `JQL_QUERY` - Query to find stale issues
- `JQL_QUERY_ICEBOX` - Query to find issues to close
- `LABEL_TO_ADD` - Label for stale issues
- `COMMENT_TO_ADD` - Comment for stale issues
- `COMMENT_TO_ADD_ICEBOX` - Comment when closing

**RCA-Specific:**
- `JIRA_RCA_ORIGIN_FIELD_NAME` - Name of Origin custom field
- `JIRA_CREATED_DATE` - Optional date filter for created issues
- `COMMENT_TO_ADD_RCA_ST` - Description for RCA sub-tasks

**Data Quality-Specific:**
- `JQL_MISSING_FIXVER`, `JQL_MISSING_ORIGIN`, etc. - JQL queries for each check
- `TEAMS_WEBHOOK_URL_V2` - Microsoft Teams webhook for notifications
- `DATA_QUALITY_EXCLUDE_PROJECTS` - Projects to exclude from reporting
- `DATA_QUALITY_FALLBACK_NAME` - Name for unmanaged issues notifications
- `DATA_QUALITY_FALLBACK_EMAIL` - Email for unmanaged issues notifications

### 5. Create Logs Directory
```bash
mkdir -p logs
```

### 6. Test Run
```bash
# Run manually first to test each module
source venv/bin/activate

# Test icebox automation
python -m jira_automation.jira_icebox

# Test RCA subtask creation
python -m jira_automation.create_rca_subtasks

# Test platform version derivation
python -m jira_automation.derive_platform_version

# Test data quality report (runs platform version derivation first)
python -m jira_automation.data_quality_report
```

### 7. Schedule (Optional)
```bash
# Edit run_icebox_job.sh to set PROJECT_DIR
nano run_icebox_job.sh

# Make executable
chmod +x run_icebox_job.sh

# Test shell script
./run_icebox_job.sh

# Add to crontab (daily at 9:00 AM on weekdays)
crontab -e
# Add: 0 9 * * 1-5 /path/to/jira_hygiene/run_icebox_job.sh
```

## 📚 Documentation

All documentation is included in the package:

- **README.md** - Complete setup, usage, troubleshooting guide (the main doc)
- **FILE_LIST.md** - Detailed description of every file in the package
- **PACKAGE_SUMMARY.md** - This quick start guide
- **Code comments** - Inline documentation in all Python files

## 🔒 Security Notes

**Before Sharing:**

1. **Never include actual .env file** - Only share .env.sample
2. **Remove any credentials** from shell scripts
3. **Review JQL queries** - May contain sensitive project names
4. **Sanitize logs** - Remove any logs with actual issue data
5. **Check comments** - Review COMMENT_TO_ADD text for sensitive info
6. **Database credentials** - Ensure DATABASE_URL is not exposed

**What's Safe to Share:**
- ✅ All Python code
- ✅ .env.sample (template only)
- ✅ Shell scripts (after removing paths)
- ✅ Configuration files (log_config.yaml)
- ✅ Documentation files

**What to Keep Private:**
- ❌ .env file (actual credentials)
- ❌ Logs directory
- ❌ Jira tokens/passwords
- ❌ Database connection strings
- ❌ Teams webhook URLs
- ❌ Specific project names (if confidential)

## 🔄 Modification for Recipients

Recipients will need to modify:

1. **`.env` file** - All Jira credentials, database URL, and settings
2. **`run_icebox_job.sh`** - Line 6: PROJECT_DIR path
3. **JQL queries in .env** - Update project names and criteria
4. **Comments in .env** - Customize message text
5. **Database schema** - Ensure required tables exist (see db_utils.py for schema)

## 💡 Module Usage Examples

### Running Specific Modules

```bash
# Icebox automation only
python -m jira_automation.jira_icebox

# Create RCA subtasks for critical bugs
python -m jira_automation.create_rca_subtasks

# Derive platform versions
python -m jira_automation.derive_platform_version

# Generate data quality report with Teams notifications
python -m jira_automation.data_quality_report
```

## 📊 Expected Output

### Icebox Console Output
```
================================================================================
                          STALE ISSUE UPDATE
================================================================================
🔍 Running JQL query to find stale issues
ℹ️  Found 15 stale issues to process
➡️  Processing issue MYPROJ-123: Old bug from last year
✅ Added label 'compdiv-icebox' to MYPROJ-123
✅ Added automated comment to MYPROJ-123
🎉 Stale issue update complete: 15 issues processed
```

### RCA Subtask Output
```
🔍 Running JQL query to find critical CRP bugs...
Found 8 critical CRP bugs to check.
Processing Ticket: PROJ-456 | Summary: 'Critical Production Bug' | Status: 'In Progress'
  -> Creating RCA sub-task for PROJ-456 using issue type ID 10003...
✅ Successfully created sub-task PROJ-457 for parent PROJ-456.
```

### Data Quality Report Output
```
================================================================================
                        DATA QUALITY REPORT
================================================================================
Connecting to Jira server at https://jira.example.com
✅ Connected to Jira version 9.4.0

Missing Fix Version Report
--------------------------
🔍 Running query
ℹ️  Found 23 issues

📊 Writing consolidated report to ./reports/data_quality_report_2025-12-16.csv
✅ Generated consolidated report
📧 Sent 5 Teams notifications to managers
✅ Data quality report generation completed successfully
```

### Log Files
- **logs/app.log** - Detailed execution log with timestamps
- **logs/cron_icebox.log** - Shell script execution log
- **reports/** - Generated CSV reports

## 🆘 Getting Help

### Common Issues

**"Could not find custom field"**
- Solution: Custom field names are case-sensitive, verify exact name in Jira

**"Authentication failure"**
- Solution: Check JIRA_TOKEN is valid and not expired

**"Database pool is not available"**
- Solution: Verify DATABASE_URL is set correctly and database is accessible

**"No transition to Closed found"**
- Solution: Verify workflow allows transition from current status

**"Teams notification failed"**
- Solution: Check TEAMS_WEBHOOK_URL_V2 is valid and webhook is active

### Support Resources

1. **README.md** - Comprehensive troubleshooting section
2. **Logs** - Check logs/app.log for detailed error messages
3. **FILE_LIST.md** - Understanding file purposes
4. **Code comments** - Inline documentation explains logic

## 🔗 Integration Options

### Standalone Script (Current)
- Run as Python script via cron
- No web server required
- Simplest setup

### API Server (Optional - Not Included)
- Requires FastAPI server
- Shell script uses curl to trigger
- More complex but allows web UI
- See main project for server code

### CI/CD Pipeline
- Can be triggered from Jenkins/GitLab/GitHub Actions
- Set environment variables in CI/CD tool
- Run as Docker container

## 📈 Monitoring

### Track Automation Success

```bash
# Count processed issues today
grep "$(date +%Y-%m-%d)" logs/app.log | grep "issues processed"

# Find errors
grep ERROR logs/app.log | tail -20

# Check last run
tail logs/cron_icebox.log

# View generated reports
ls -lh reports/
```

### Jira Reporting

```jql
# View all issues labeled by icebox automation
labels = compdiv-icebox
AND comment ~ "THIS IS AN AUTOMATED MESSAGE"
ORDER BY updated DESC

# View recently closed by automation
status = Closed
AND resolution in ("Won't Do", "Won't Fix")
AND updated >= -7d
AND comment ~ "THIS IS AN AUTOMATED MESSAGE"

# View RCA subtasks created
summary ~ "Root Cause Analysis(RCA)"
AND type = Sub-task
AND created >= -30d
```

## 🎓 Best Practices

1. **Test first** - Run manually with small JQL results
2. **Monitor logs** - Check daily for errors
3. **Rotate tokens** - Update JIRA_TOKEN quarterly
4. **Backup config** - Keep .env.sample updated
5. **Document changes** - Note any customizations
6. **Review quarterly** - Adjust JQL and timeframes as needed
7. **Verify Teams webhooks** - Test notifications before production use
8. **Database backups** - Regular backups of PostgreSQL data

## 📞 Package Information

- **Created**: 2025-12-16
- **Python Version**: 3.8+
- **Dependencies**: jira, python-dotenv, pyyaml, psycopg2-binary, requests, fastapi, uvicorn
- **Tested On**: Jira Cloud & Jira Data Center
- **License**: Internal use

---

## Next Steps

1. ✅ Extract package to desired location
2. ✅ Read README.md for detailed setup
3. ✅ Configure .env with your settings (including DATABASE_URL)
4. ✅ Set up PostgreSQL database with required tables
5. ✅ Configure Teams webhooks for notifications
6. ✅ Test run each module manually
7. ✅ Schedule via cron
8. ✅ Monitor logs and reports

**Ready to share!** This package contains everything needed to run comprehensive Jira hygiene automation independently.
