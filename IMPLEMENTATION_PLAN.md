# Implementation Plan: Enhanced Burndown Tracking for Closed Epics

## Executive Summary
Extend the existing IRIS closure logic to COMPDIV epics and enhance the dashboard to visually indicate completed epics while maintaining their historical burndown data.

---

## Key Decisions (APPROVED)

### 1. Reopening Epics
**Decision**: Manual intervention required for reopening closed epics

**Rationale**:
- Prevents accidental data changes from automated processes
- Provides clear audit trail for status changes
- Requires deliberate action to reactivate an epic

**Implementation**:
- Closure function will NOT automatically reactivate epics that are reopened in Jira
- Database updates to reopen require manual SQL or future admin interface

### 2. COMPDIV Filtering
**Decision**: Close ALL COMPDIV epics regardless of `filter_flag`

**Rationale**:
- Epic closure is a status change, not a filtering criterion
- `filter_flag` is for organizational/reporting purposes only
- Ensures data consistency across all COMPDIV epics

**Implementation**:
- Closure query: `WHERE issue_key ~ '^COMPDIV-\d+$'` (no filter_flag check)
- Burndown queries: Continue to respect `filter_flag` for processing

### 3. Dashboard Sorting
**Decision**: Two-tier sorting - Status first (active at top, closed at bottom), then alphabetically by issue_key

**Rationale**:
- Active epics are the primary focus and should be most visible
- Closed epics remain accessible for historical reference
- Alphabetical sorting within each group aids navigation

**Implementation**:
- Sort order:
  1. Primary: `is_active DESC` (True/active first, False/closed last)
  2. Secondary: `epic_key ASC` (alphabetical A-Z)
- Applied to Overview, BIGINT, and IRIS tabs

### 4. Historical Data Collection
**Decision**: Continue collecting burndown data for ALL epics (both active and closed)

**Rationale**:
- Maintains complete historical trend visibility
- Allows retrospective analysis of completion timelines
- Zero-point tracking shows when work stopped

**Implementation**:
- Remove skip logic for closed epics in both COMPDIV and IRIS burndown functions
- Database continues to receive daily updates for closed epics (will show flat zero-point lines)

---

## Phase 1: Database & Core Logic Updates

### 1.1 Create Unified Closure Function
**File**: `jira_data_analysis/initiative_children.py`

**New function**: `close_completed_initiatives(jira, db_pool, initiative_type=None)`

```python
def close_completed_initiatives(jira, db_pool, initiative_type=None):
    """
    Checks initiatives and closes them if they are in a closed statusCategory.
    Sets eff_end_date to current date and active_flag to false for closed initiatives.

    Args:
        jira: Jira client instance
        db_pool: Database connection pool
        initiative_type: 'IRIS', 'COMPDIV', or None (for all)
    """
```

**Query logic**:
```sql
-- For IRIS
SELECT issue_key
FROM tbl_initiative_issue_keys
WHERE "IRIS" = true
  AND (active_flag IS NULL OR active_flag = true)

-- For COMPDIV
SELECT issue_key
FROM tbl_initiative_issue_keys
WHERE issue_key ~ '^COMPDIV-\d+$'
  AND (active_flag IS NULL OR active_flag = true)

-- For ALL (initiative_type=None)
SELECT issue_key
FROM tbl_initiative_issue_keys
WHERE (active_flag IS NULL OR active_flag = true)
```

**Update logic**:
```sql
UPDATE tbl_initiative_issue_keys
SET eff_end_date = CURRENT_DATE, active_flag = false
WHERE issue_key = ANY(%s)
```

**Error handling**:
- Batch Jira queries in chunks of 100 to avoid API limits
- Continue processing on chunk failures
- Log all closures with epic keys and timestamps

**Wrapper functions**:
- Keep existing: `close_completed_iris_initiatives()` → calls with `initiative_type='IRIS'`
- Add new: `close_completed_compdiv_initiatives()` → calls with `initiative_type='COMPDIV'`

---

### 1.2 Update COMPDIV Burndown Query Logic
**File**: `jira_automation/compdiv_burndown.py`

**Function**: `run_for_all_compdiv_epics()` (lines 489-592)

**Changes**:
1. **Update database query** (lines 514-534):
   ```python
   # OLD:
   if filter_flag:
       base_sql = """
           SELECT DISTINCT issue_key
           FROM public.tbl_initiative_issue_keys
           WHERE filter_flag = %s
       """
   else:
       base_sql = """
           SELECT DISTINCT issue_key
           FROM public.tbl_initiative_issue_keys
           WHERE issue_key ~ '^COMPDIV-\d+$'
       """

   # NEW:
   if filter_flag:
       base_sql = """
           SELECT DISTINCT issue_key
           FROM public.tbl_initiative_issue_keys
           WHERE (active_flag IS NULL OR active_flag = true OR active_flag = false)
             AND filter_flag = %s
       """
   else:
       base_sql = """
           SELECT DISTINCT issue_key
           FROM public.tbl_initiative_issue_keys
           WHERE issue_key ~ '^COMPDIV-\d+$'
             AND (active_flag IS NULL OR active_flag = true OR active_flag = false)
       """
   ```

2. **Remove skip logic for closed epics** (DELETE lines 549-552):
   ```python
   # DELETE THIS BLOCK:
   is_closed, epic_status_name = get_epic_status_info(epic)
   if is_closed:
       logger.info("Skipping %s: epic status is closed (%s)", epic, epic_status_name)
       continue
   ```

3. **Keep status logging** (modify existing log):
   ```python
   is_closed, epic_status_name = get_epic_status_info(epic)
   logger.info("COMPDIV burndown start: %s (status: %s, closed: %s)", epic, epic_status_name, is_closed)
   ```

---

### 1.3 Update IRIS Burndown Query Logic
**File**: `jira_automation/iris_burndown.py`

**Function**: `run_for_all_iris_epics()` (lines 486-555)

**Changes**:
1. **Update database query** (lines 501-507):
   ```python
   # OLD:
   sql = """
       SELECT issue_key
       FROM public.tbl_initiative_issue_keys
       WHERE "IRIS" = true
         AND active_flag IS NULL
       GROUP BY issue_key
   """

   # NEW:
   sql = """
       SELECT issue_key
       FROM public.tbl_initiative_issue_keys
       WHERE "IRIS" = true
         AND (active_flag IS NULL OR active_flag = true OR active_flag = false)
       GROUP BY issue_key
   """
   ```

2. **Remove skip logic for closed epics** (DELETE lines 523-526):
   ```python
   # DELETE THIS BLOCK:
   is_closed, epic_status_name = get_epic_status_info(epic)
   if is_closed:
       logger.info("Skipping %s: epic status is closed (%s)", epic, epic_status_name)
       continue
   ```

3. **Keep status logging** (modify existing log):
   ```python
   is_closed, epic_status_name = get_epic_status_info(epic)
   logger.info("IRIS burndown start: %s (status: %s, closed: %s)", epic, epic_status_name, is_closed)
   ```

---

## Phase 2: Dashboard Visual Enhancements

### 2.1 Fetch Epic Status for Dashboard
**File**: `jira_automation/generate_burndown_dashboard.py`

**New function** (add after imports):
```python
def get_epic_status_from_db(epic_key: str, db_pool) -> Tuple[bool, str]:
    """
    Fetch epic status from tbl_initiative_issue_keys.

    Returns:
        Tuple of (is_active, eff_end_date_str)
        - is_active: True if active_flag is NULL/True, False otherwise
        - eff_end_date_str: Date string or empty string if not closed
    """
    from jira_data_analysis import db_utils

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
                is_active = active_flag is None or active_flag is True
                eff_end_date_str = eff_end_date.strftime('%Y-%m-%d') if eff_end_date and not is_active else ''
                return is_active, eff_end_date_str
    except Exception as e:
        logger.debug(f"Could not fetch status for {epic_key}: {e}")
    finally:
        db_pool.putconn(conn)

    # Default: assume active if not found
    return True, ''
```

**Modify**: `collect_html_files()` function (lines 23-62)
- Add database pool parameter
- Fetch status for each epic_key extracted from filename

**Modify**: `generate_dashboard_html()` function (lines 107-171)
- Add database pool initialization at start
- Pass db_pool to collect_html_files()
- Update chart metadata dictionaries (lines 131-158) to include:
  ```python
  {
      'filename': filename,
      'title': title,
      'epic_key': epic_key,
      'is_active': is_active,
      'eff_end_date': eff_end_date,
      'path': filepath
  }
  ```

---

### 2.2 Update Dashboard Sorting
**File**: `jira_automation/generate_burndown_dashboard.py`

**Modify**: `collect_html_files()` function (lines 50-57)
- Replace alphabetical sort with two-tier sort:
  ```python
  # OLD:
  overview_files.sort()
  bigint_files.sort()
  iris_files.sort()

  # NEW (after building chart metadata lists):
  # Sort by status (active first) then by epic_key alphabetically
  overview_charts.sort(key=lambda x: (not x.get('is_active', True), x.get('epic_key', '')))
  bigint_charts.sort(key=lambda x: (not x.get('is_active', True), x.get('epic_key', '')))
  iris_charts.sort(key=lambda x: (not x.get('is_active', True), x.get('epic_key', '')))
  ```

---

### 2.3 Update Dashboard Styling
**File**: `jira_automation/generate_burndown_dashboard.py`

**Modify**: `generate_grid_html()` function (lines 187-211)
```python
def generate_grid_html(charts: List[dict]) -> str:
    """Generate the 3-column grid HTML for a list of charts."""
    if not charts:
        return '<p style="text-align: center; padding: 40px; color: #666;">No charts available</p>'

    grid_html = '<div class="chart-grid">\n'
    for chart in charts:
        # Create clickable title if epic_key exists
        if chart.get('epic_key'):
            jira_url = f"https://rndjira.sas.com/browse/{chart['epic_key']}"

            # NEW: Check if epic is closed and add visual indicator
            is_active = chart.get('is_active', True)
            title_class = "epic-link"

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
```

**Modify**: CSS styles in `generate_html_structure()` (add after line 380):
```css
.chart-title .epic-link.completed-epic {
    color: #c62828;  /* Bold red */
    font-weight: 700;
}

.chart-title .epic-link.completed-epic:hover {
    color: #b71c1c;  /* Darker red on hover */
}

.completed-badge {
    display: inline-block;
    font-size: 11px;
    font-weight: 700;
    color: #c62828;
    margin-left: 8px;
    padding: 2px 6px;
    background-color: #ffebee;
    border-radius: 3px;
    border: 1px solid #ef9a9a;
}
```

---

## Phase 3: Integration & Scheduling

### 3.1 Update Daily Job
**File**: `jira_server/tasks.py`

**Locate**: `run_jira_export_task()` function

**Add after existing initiative sync**:
```python
from jira_data_analysis.initiative_children import close_completed_initiatives

def run_jira_export_task():
    # ... existing code ...

    # After sync_initiatives_from_jql() call:
    logger.processing("Checking for completed initiatives to close")
    try:
        close_completed_initiatives(jira_client, db_pool, initiative_type=None)
        logger.success("Completed initiative closure check")
    except Exception as e:
        logger.error(f"Failed to close completed initiatives: {e}")

    # ... rest of existing code ...
```

### 3.2 Update Job Endpoints
**File**: `jira_server/main.py`

**Optional**: Add standalone endpoint for closure checks:
```python
@app.post("/jobs/close-completed-initiatives", status_code=202, summary="Close completed COMPDIV/IRIS initiatives")
async def trigger_close_completed_initiatives(background_tasks: BackgroundTasks):
    logger.info("Close completed initiatives endpoint triggered via API")
    logger.processing("Scheduling close completed initiatives background task")
    background_tasks.add_task(run_close_completed_initiatives_task)
    logger.success("Close completed initiatives scheduled")
    return {"message": "Close completed initiatives job scheduled", "status": "scheduled"}
```

**File**: `jira_server/tasks.py` (add new task):
```python
def run_close_completed_initiatives_task():
    """Task wrapper for closing completed initiatives."""
    from jira_data_analysis.initiative_children import close_completed_initiatives

    logger.start("Starting close completed initiatives task")
    jira_client = get_jira_client()
    db_pool = db_utils.get_connection_pool()

    try:
        close_completed_initiatives(jira_client, db_pool, initiative_type=None)
        logger.complete("Close completed initiatives task completed successfully")
    except Exception as e:
        logger.exception(f"Close completed initiatives task failed: {e}")
```

### 3.3 Cron Schedule
**File**: `crontab_schedules.txt` (documentation)

Add note that closure check runs as part of daily job:
```bash
# Daily sync + initiative closure check + icebox at 9:00 AM weekdays
0 9 * * 1-5 /path/to/jira_server/run_daily_job.sh
```

---

## Phase 4: Testing & Validation

### 4.1 Unit Testing Checklist

**Test: Closure Function**
- [ ] IRIS epic that is closed in Jira → Updates DB correctly
- [ ] COMPDIV epic that is closed in Jira → Updates DB correctly
- [ ] Epic with `active_flag = false` already → No duplicate update
- [ ] Epic closed then reopened in Jira → Remains closed in DB (manual intervention required)
- [ ] Batch processing of 150 epics → Handles pagination correctly
- [ ] Jira API failure → Logs error, continues processing remaining batches

**Test: Burndown Data Collection**
- [ ] Closed COMPDIV epic → Still processes and stores data
- [ ] Closed IRIS epic → Still processes and stores data
- [ ] Data shows zero/flat trend after closure → Confirms no new work
- [ ] `filter_flag` filtering → Still respected for COMPDIV processing

**Test: Dashboard Display**
- [ ] Active epic → Normal display (black text)
- [ ] Closed epic → Bold red text with "[COMPLETED: DATE]" badge
- [ ] Sorting → Active epics at top, closed at bottom, alphabetical within each group
- [ ] All three tabs (Overview, BIGINT, IRIS) → Consistent behavior
- [ ] Epic with no DB record → Defaults to active display

### 4.2 Integration Testing Scenarios

**Scenario 1: Complete Workflow**
1. Create new COMPDIV epic in Jira
2. Add to `tbl_initiative_issue_keys` via JQL sync
3. Run burndown → Verify data collected
4. Close epic in Jira
5. Run closure check → Verify DB updated
6. Run burndown again → Verify still processes
7. Regenerate dashboard → Verify red header

**Scenario 2: Mixed Status Dashboard**
1. Have 3 active and 2 closed COMPDIV epics
2. Generate dashboard
3. Verify order: COMPDIV-100 (active), COMPDIV-200 (active), COMPDIV-300 (active), COMPDIV-150 (closed), COMPDIV-250 (closed)

**Scenario 3: Manual Reopening**
1. Closed epic in DB (active_flag=false)
2. Reopen in Jira
3. Run closure check → Epic remains closed in DB
4. Manual SQL to reopen:
   ```sql
   UPDATE tbl_initiative_issue_keys
   SET active_flag = NULL, eff_end_date = NULL
   WHERE issue_key = 'COMPDIV-XXX';
   ```
5. Verify burndown and dashboard reflect active status

### 4.3 Edge Case Handling

**Edge Case**: Epic not in `tbl_initiative_issue_keys`
- **Expected**: Closure function skips (only processes known epics)
- **Resolution**: Ensure JQL sync runs before closure check

**Edge Case**: Partial Jira API failure
- **Expected**: Function logs error, continues with remaining batches
- **Resolution**: Review logs, retry failed batch manually if needed

**Edge Case**: Database connection lost mid-update
- **Expected**: Transaction rollback, no partial updates
- **Resolution**: Re-run closure check on next scheduled run

---

## Phase 5: Documentation Updates

### 5.1 Update README.md

**Section**: Burndown Analysis (around line 450)

Add subsection:
```markdown
#### Epic Lifecycle & Closure

Both COMPDIV and IRIS burndowns track epics through their entire lifecycle, including after completion:

**Automatic Closure**:
- Daily job checks all epics in Jira for closed statusCategory
- Sets `eff_end_date = CURRENT_DATE` and `active_flag = false` in `tbl_initiative_issue_keys`
- Burndown data collection continues for historical tracking (will show flat zero-point lines)

**Dashboard Display**:
- Active epics: Normal display at top of each tab
- Completed epics: **Bold red header** with "[COMPLETED: YYYY-MM-DD]" badge at bottom of each tab
- Sorting: Status (active first) → Alphabetical by epic key

**Manual Reopening**:
Epics closed in the database require manual intervention to reactivate:
```sql
UPDATE tbl_initiative_issue_keys
SET active_flag = NULL, eff_end_date = NULL
WHERE issue_key = 'EPIC-KEY';
```

**Related Functions**:
- `initiative_children.close_completed_initiatives()` - Checks and closes epics
- `compdiv_burndown.run_for_all_compdiv_epics()` - Processes all epics (active + closed)
- `iris_burndown.run_for_all_iris_epics()` - Processes all epics (active + closed)
```

### 5.2 Update CLAUDE.md

**Add new workflow section**:
```markdown
### Managing Completed Epics

**Automatic Closure Workflow**:
1. Daily job runs `close_completed_initiatives()` after data sync
2. Function queries all active epics from `tbl_initiative_issue_keys`
3. Checks each epic's statusCategory in Jira
4. Updates DB for closed epics:
   - `eff_end_date = CURRENT_DATE`
   - `active_flag = false`

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

**Dashboard Behavior**:
- Completed epics display with bold red headers
- Sorted to bottom of their respective tabs
- Historical burndown data remains visible
```

### 5.3 Add Migration Notes

**File**: Create `jira_server/schema_migrations/004_epic_closure_tracking.md`

```markdown
# Migration 004: Epic Closure Tracking

## Summary
Enhanced epic lifecycle tracking to automatically close completed epics and maintain historical burndown data.

## Changes

### Database Schema
No schema changes required. Uses existing columns:
- `tbl_initiative_issue_keys.active_flag` (BOOLEAN)
- `tbl_initiative_issue_keys.eff_end_date` (DATE)

### Application Logic
1. Created unified `close_completed_initiatives()` function
2. Updated COMPDIV and IRIS burndown queries to include closed epics
3. Enhanced dashboard to visually distinguish completed epics

### Backward Compatibility
✅ Fully backward compatible
- Existing NULL `active_flag` values treated as active
- No changes to database schema
- Dashboard gracefully handles missing status information

## Deployment Steps

1. Deploy code changes (no downtime required)
2. Run initial closure check manually:
   ```bash
   curl -X POST http://127.0.0.1:8000/jobs/close-completed-initiatives
   ```
3. Verify logs for closed epics
4. Regenerate dashboard:
   ```bash
   python -m jira_automation.generate_burndown_dashboard
   ```
5. Review dashboard for correct display of completed epics

## Rollback Plan

If rollback needed:
1. Revert code to previous version
2. Database state is safe (no destructive changes)
3. Manually update any incorrectly closed epics if needed

## Testing Performed

- [x] Closure function with IRIS epics
- [x] Closure function with COMPDIV epics
- [x] Dashboard sorting and styling
- [x] Burndown data collection for closed epics
- [x] Error handling for Jira API failures
```

---

## Implementation Checklist

### Phase 1: Core Logic
- [ ] Create `close_completed_initiatives()` in `initiative_children.py`
- [ ] Update `close_completed_iris_initiatives()` to use new function
- [ ] Add `close_completed_compdiv_initiatives()` wrapper
- [ ] Update COMPDIV burndown query (remove skip logic)
- [ ] Update IRIS burndown query (remove skip logic)
- [ ] Test closure function with sample epics

### Phase 2: Dashboard
- [ ] Add `get_epic_status_from_db()` function
- [ ] Update `collect_html_files()` to fetch status
- [ ] Update chart metadata to include status fields
- [ ] Implement two-tier sorting (status → alphabetical)
- [ ] Update `generate_grid_html()` for completed epic styling
- [ ] Add CSS for completed epic badges
- [ ] Test dashboard with mixed active/closed epics

### Phase 3: Integration
- [ ] Add closure check to daily job (`tasks.py`)
- [ ] Optional: Add standalone closure endpoint
- [ ] Test end-to-end workflow
- [ ] Update cron documentation

### Phase 4: Testing
- [ ] Run unit tests (all checklist items above)
- [ ] Run integration scenarios
- [ ] Verify edge case handling
- [ ] Performance test with 100+ epics

### Phase 5: Documentation
- [ ] Update README.md
- [ ] Update CLAUDE.md
- [ ] Create migration notes
- [ ] Document manual reopening procedure

---

## Success Criteria

✅ **Functional Requirements**:
1. Closed epics in Jira automatically update DB with `eff_end_date` and `active_flag=false`
2. Burndown data continues to be collected for closed epics
3. Dashboard displays completed epics with bold red headers and completion date
4. Dashboard sorts active epics at top, closed at bottom, alphabetically within each group

✅ **Non-Functional Requirements**:
1. No manual intervention required for normal closure workflow
2. No data loss or corruption during closure process
3. Dashboard loads in < 3 seconds with 50+ epics
4. Clear logs for all closure actions

✅ **Documentation**:
1. All workflows documented in README and CLAUDE.md
2. Manual reopening procedure clearly explained
3. Migration notes created for deployment reference

---

## Timeline Estimate

- **Phase 1 (Core Logic)**: 2-3 hours
- **Phase 2 (Dashboard)**: 2-3 hours
- **Phase 3 (Integration)**: 1 hour
- **Phase 4 (Testing)**: 2-3 hours
- **Phase 5 (Documentation)**: 1 hour

**Total**: 8-11 hours

---

## Suggested Commit Messages

```
Phase 1.1: Add unified initiative closure logic for COMPDIV and IRIS epics

- Create close_completed_initiatives() function in initiative_children.py
- Refactor close_completed_iris_initiatives() to use unified function
- Add close_completed_compdiv_initiatives() wrapper for COMPDIV epics
- Support filtering by initiative type (IRIS/COMPDIV/all)
```

```
Phase 1.2-1.3: Update burndown queries to include closed epics

- Modify COMPDIV burndown to process all epics regardless of active_flag
- Modify IRIS burndown to process all epics regardless of active_flag
- Remove skip logic for closed epics in both burndown functions
- Maintain historical data collection for trend analysis
```

```
Phase 2: Enhance dashboard to display completed epics with visual indicators

- Add get_epic_status_from_db() to fetch active_flag and eff_end_date
- Implement two-tier sorting: status (active first) then alphabetical
- Add bold red headers and [COMPLETED: DATE] badges for closed epics
- Add CSS styling for completed-epic class and badges
```

```
Phase 3: Integrate epic closure checks into daily job workflow

- Add close_completed_initiatives() call to run_jira_export_task()
- Optional: Add standalone /jobs/close-completed-initiatives endpoint
- Update task orchestration for automated closure checks
```

```
Phase 5: Document epic closure workflow and manual reopening procedures

- Update README.md with epic lifecycle documentation
- Update CLAUDE.md with closure workflow details
- Add migration notes for deployment reference
- Document manual reopening procedure for edge cases
```
