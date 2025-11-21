# Interactive Bug Table Implementation

## Overview
Enhanced the "Bugs by Release (Current Snapshot)" chart with interactive functionality. When users click on an "Open" bugs column, a table appears below the chart showing detailed information about all open bugs for that release.

## Changes Made

### 1. Database Schema Migration
**File**: `jira_server/schema_migrations/005_add_summary_updated_to_bug_snapshots.sql`

Added two new columns to `tbl_bug_snapshots`:
- `summary` (TEXT): Issue summary/title from Jira
- `updated` (TIMESTAMP): Last modified timestamp from Jira

**Action Required**: Run the migration script before using the new functionality:
```bash
psql $DATABASE_URL -f jira_server/schema_migrations/005_add_summary_updated_to_bug_snapshots.sql
```

### 2. Bug Snapshot Collection Enhancement
**File**: `jira_server/jira_automation/collect_bug_snapshots.py`

Modified to collect and store:
- Issue summary field
- Last updated timestamp

These fields are now included in the daily bug snapshot collection.

### 3. Chart Generation Enhancement
**File**: `jira_server/jira_automation/generate_bug_charts.py`

#### Data Processing Changes:
- Modified SQL query to select `summary` and `updated` columns
- Added logic to extract open bug details by release version
- Created `bug_details_by_release` dictionary mapping releases to bug lists
- Passed detailed bug data to HTML generation

#### HTML/JavaScript Changes:
- Added CSS styling for interactive bug details table
- Embedded bug details as JSON in HTML
- Added Plotly click event handler for the "Bugs by Release" chart
- Implemented dynamic table rendering on click
- Added smooth scrolling to table when displayed

## Features

### User Interaction Flow
1. User views the "Bugs by Release (Current Snapshot)" chart
2. User clicks on an **Open** bugs column (blue bar)
3. A table appears below the chart showing all open bugs for that release
4. Each row in the table contains:
   - **Issue ID** (clickable link to Jira)
   - **Summary** (issue title)
   - **Last Modified** (timestamp)
5. Clicking on an Issue ID opens the bug in a new browser tab

### Behavior Notes
- **Only Open bugs trigger the table**: Clicking on "Closed" bugs (orange bars) hides the table
- **Smooth scrolling**: Page automatically scrolls to show the table
- **Responsive design**: Table matches the dashboard styling
- **Empty state**: Shows a message if no open bugs exist for the release

## Deployment Steps

### Step 1: Run Database Migration
```bash
# Connect to your database
psql $DATABASE_URL

# Run the migration
\i jira_server/schema_migrations/005_add_summary_updated_to_bug_snapshots.sql

# Verify columns were added
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'tbl_bug_snapshots'
AND column_name IN ('summary', 'updated');
```

### Step 2: Collect Fresh Bug Snapshots
After running the migration, collect new snapshots to populate the new fields:

```bash
# Option 1: Trigger via API endpoint
curl -X POST http://127.0.0.1:8000/jobs/collect-bug-snapshots

# Option 2: Run directly (from jira_server directory)
cd jira_server
source venv/bin/activate
python -m jira_automation.collect_bug_snapshots
```

### Step 3: Regenerate Bug Charts
Generate the updated HTML report with interactive functionality:

```bash
# Option 1: Trigger via API endpoint
curl -X POST http://127.0.0.1:8000/jobs/generate-bug-charts

# Option 2: Run directly (from jira_server directory)
cd jira_server
source venv/bin/activate
python -m jira_automation.generate_bug_charts
```

### Step 4: Verify the Report
Open the generated report in your browser:
- **Local path**: `jira_server/reports/bug_trends_report.html`
- **Dashboard integration**: Navigate to the Bug Trends tab in the COMPDIV Burndown Dashboard

## Testing the Feature

1. **Open the bug trends report** in a web browser
2. **Navigate to** the "Bugs by Release (Current Snapshot)" chart
3. **Click on a blue "Open" bar** for any release version
4. **Verify**:
   - Table appears below the chart
   - Header shows the release version and bug count
   - Table contains three columns: Issue ID, Summary, Last Modified
   - Issue IDs are clickable links
   - Clicking an Issue ID opens Jira in a new tab
5. **Click on an orange "Closed" bar**: Table should disappear
6. **Click on different "Open" bars**: Table should update with new bug lists

## Technical Details

### Data Flow
1. **Collection**: `collect_bug_snapshots.py` fetches bugs with summary and updated fields from Jira
2. **Storage**: Data stored in `tbl_bug_snapshots` table
3. **Processing**: `generate_bug_charts.py` queries latest snapshot and groups by release/state
4. **Rendering**: Bug details embedded as JSON in HTML, JavaScript handles click events

### JavaScript Implementation
- Uses Plotly's `plotly_click` event to detect bar clicks
- Filters out "Closed" bar clicks (only "Open" bars trigger table)
- Dynamically generates HTML table from JSON data
- Uses smooth scrolling for better UX

### Jira Link Format
All Issue ID links use the format:
```
https://rndjira.sas.com/browse/[ISSUE-KEY]
```
Links open in new browser tabs via `target="_blank"`

## Troubleshooting

### Issue: Table doesn't appear when clicking
- **Check browser console** for JavaScript errors
- **Verify** bug_details_by_release JSON is embedded (View Page Source)
- **Ensure** you're clicking on "Open" (blue) bars, not "Closed" (orange) bars

### Issue: Table shows "N/A" for summary or modified date
- **Run migration**: Ensure database columns exist
- **Collect new snapshots**: Old snapshots won't have the new fields
- **Check data**: Query `tbl_bug_snapshots` to verify summary/updated are populated

### Issue: Links don't work
- **Verify URL format**: Should be `https://rndjira.sas.com/browse/[KEY]`
- **Check browser**: Ensure pop-up blocker isn't preventing new tabs

## Future Enhancements (Optional)
- Add filtering/sorting to the bug table
- Export table data to CSV
- Add additional columns (assignee, priority, etc.)
- Show table for Closed bugs as well
- Add search/filter functionality within the table

## Commit Message Suggestion
```
feat: Add interactive bug details table to Bugs by Release chart

- Add summary and updated columns to tbl_bug_snapshots
- Update bug snapshot collection to fetch summary and last modified date
- Enhance chart generation with click-to-view bug details
- Display clickable table with Issue ID, Summary, and Modified Date
- Links open Jira issues in new tabs when clicked
```
