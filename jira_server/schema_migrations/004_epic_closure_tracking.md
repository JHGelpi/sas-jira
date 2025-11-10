# Migration 004: Epic Closure Tracking & Dashboard Enhancements

**Date**: 2025-11-10
**Type**: Feature Enhancement
**Risk Level**: Low (No schema changes, backward compatible)

---

## Summary

Enhanced epic lifecycle tracking to automatically close completed epics and maintain historical burndown data. Improved dashboard with visual indicators for completed epics.

---

## Changes Overview

### 1. Database Logic (READ/UPDATE Only)
- **NO SCHEMA CHANGES** - Uses existing columns in `tbl_initiative_issue_keys`
- Only updates metadata: `eff_end_date` and `active_flag`
- Burndown data tables (`tbl_compdiv_burndown`, `tbl_iris_burndown`) are **NEVER** modified

### 2. Application Logic
- Created unified `close_completed_initiatives()` function
- Updated COMPDIV and IRIS burndown queries to include closed epics
- Enhanced dashboard to visually distinguish completed epics

### 3. Integration
- Daily job now closes both IRIS and COMPDIV completed epics
- Dashboard generates with active/closed sorting and visual indicators

---

## Files Modified

### Core Logic
1. **`jira_data_analysis/initiative_children.py`**
   - Added: `close_completed_initiatives(jira, db_pool, initiative_type=None)`
   - Added: `close_completed_compdiv_initiatives(jira, db_pool)`
   - Modified: `close_completed_iris_initiatives()` now uses unified function

2. **`jira_automation/compdiv_burndown.py`**
   - Updated: Query includes all epics `(active_flag IS NULL OR true OR false)`
   - Removed: Skip logic for closed epics (lines 550-552)
   - Added: Enhanced status logging (ACTIVE/CLOSED labels)

3. **`jira_automation/iris_burndown.py`**
   - Updated: Query includes all epics `(active_flag IS NULL OR true OR false)`
   - Removed: Skip logic for closed epics (lines 524-526)
   - Added: Enhanced status logging (ACTIVE/CLOSED labels)

### Dashboard Enhancements
4. **`jira_automation/generate_burndown_dashboard.py`**
   - Added: `get_epic_status_from_db()` - Read-only status lookup
   - Updated: Chart metadata includes `is_active` and `eff_end_date`
   - Added: Two-tier sorting (active first, then alphabetical)
   - Added: CSS styling for completed epics (bold red with badge)

### Integration
5. **`jira_server/tasks.py`**
   - Updated: `run_jira_export_task()` calls unified closure function
   - Changed: From IRIS-only to ALL initiatives (initiative_type=None)

### Documentation
6. **`README.md`**
   - Added: "Epic Lifecycle & Closure" section
   - Updated: Dashboard features documentation
   - Updated: `tbl_initiative_issue_keys` table documentation

7. **`CLAUDE.md`**
   - Added: "Managing Completed Epics" workflow section
   - Documented: Manual reopening procedures
   - Added: SQL verification queries

---

## Data Safety Guarantees

### What Is Modified
✅ **ONLY** `tbl_initiative_issue_keys` columns:
- `eff_end_date` (DATE) - Set to current date when epic closes
- `active_flag` (BOOLEAN) - Set to false when epic closes

### What Is NEVER Modified
❌ `tbl_compdiv_burndown` - 100% untouched, all historical data preserved
❌ `tbl_iris_burndown` - 100% untouched, all historical data preserved
❌ Any other burndown or analysis tables

### Reversibility
All changes are fully reversible:
```sql
-- Reopen an epic
UPDATE tbl_initiative_issue_keys
SET active_flag = NULL, eff_end_date = NULL
WHERE issue_key = 'COMPDIV-XXX';
```

---

## Deployment Steps

### Pre-Deployment Checklist
- [ ] Verify FastAPI server is running
- [ ] Confirm database connection is healthy
- [ ] Review current active epics count:
  ```sql
  SELECT COUNT(*) FROM tbl_initiative_issue_keys WHERE active_flag IS NULL;
  ```

### Deployment Process

1. **Deploy Code** (No downtime required)
   ```bash
   cd /path/to/jira_server
   git pull origin main
   source venv/bin/activate
   pip install -r requirements.txt  # If dependencies changed
   ```

2. **Restart FastAPI Server**
   ```bash
   # Stop existing server
   pkill -f uvicorn

   # Start with new code
   ./run_app.sh
   ```

3. **Verify Server Health**
   ```bash
   curl http://127.0.0.1:8000/health
   # Expected: {"status": "healthy"}
   ```

4. **Trigger Initial Closure Check** (Optional but recommended)
   ```bash
   curl -X POST http://127.0.0.1:8000/jobs/daily
   ```

5. **Monitor Logs**
   ```bash
   tail -f logs/app.log | grep -i "close completed"
   # Look for: "Successfully closed N initiatives"
   ```

6. **Verify Database Updates**
   ```sql
   -- Check for newly closed epics
   SELECT issue_key, active_flag, eff_end_date
   FROM tbl_initiative_issue_keys
   WHERE active_flag = false
   ORDER BY eff_end_date DESC
   LIMIT 10;
   ```

7. **Regenerate Dashboard**
   ```bash
   curl -X POST http://127.0.0.1:8000/jobs/generate-burndown-dashboard
   # Or run directly:
   cd jira_server
   source venv/bin/activate
   python -m jira_automation.generate_burndown_dashboard
   ```

8. **Visual Verification**
   - Open `reports/compdiv_burndown/dashboard.html` in browser
   - Verify: Active epics at top, closed epics at bottom
   - Verify: Closed epics have bold red headers with "[COMPLETED: DATE]" badges
   - Verify: All tabs (Overview, BIGINT, IRIS) display correctly

### Post-Deployment Validation

1. **Test Burndown Processing**
   ```bash
   # Run COMPDIV burndown
   curl -X POST http://127.0.0.1:8000/jobs/compdiv-burndown

   # Check logs for closed epic processing
   tail -f logs/app.log | grep "CLOSED"
   # Expected: "COMPDIV burndown start: EPIC-KEY (status: CLOSED - Done)"
   ```

2. **Verify Data Integrity**
   ```sql
   -- Ensure no burndown data was deleted
   SELECT COUNT(*) FROM tbl_compdiv_burndown;
   SELECT COUNT(*) FROM tbl_iris_burndown;
   -- Compare counts with pre-deployment

   -- Check closure updates
   SELECT
     COUNT(*) as total_epics,
     COUNT(*) FILTER (WHERE active_flag IS NULL) as active_null,
     COUNT(*) FILTER (WHERE active_flag = true) as active_true,
     COUNT(*) FILTER (WHERE active_flag = false) as closed
   FROM tbl_initiative_issue_keys;
   ```

3. **Test Historical Data Continuity**
   - Pick a closed epic
   - Verify its burndown chart exists: `{epic_key}_burndown.html`
   - Verify trend line shows historical data + flat line after closure

---

## Rollback Plan

### If Issues Are Detected

1. **Revert Code**
   ```bash
   cd /path/to/jira_server
   git revert <commit_sha>
   ./run_app.sh  # Restart server
   ```

2. **Database State**
   - **No rollback needed** - Database state is safe
   - If specific epics were incorrectly closed:
     ```sql
     UPDATE tbl_initiative_issue_keys
     SET active_flag = NULL, eff_end_date = NULL
     WHERE issue_key IN ('EPIC1', 'EPIC2', ...);
     ```

3. **Dashboard Regeneration**
   ```bash
   # Regenerate with old code
   python -m jira_automation.generate_burndown_dashboard
   ```

---

## Testing Performed

### Unit Testing
- [x] Closure function with IRIS epics
- [x] Closure function with COMPDIV epics
- [x] Closure function with mixed statuses
- [x] Query logic includes all active_flag values
- [x] Dashboard sorting (active first, then alphabetical)
- [x] Dashboard styling for completed epics

### Integration Testing
- [x] Daily job triggers closure check
- [x] Burndown processes closed epics
- [x] Dashboard generates with correct visual indicators
- [x] Error handling for Jira API failures
- [x] Database transaction rollback on errors

### Data Integrity Testing
- [x] No modifications to burndown data tables
- [x] Only metadata updates in tbl_initiative_issue_keys
- [x] Historical data preserved after closure
- [x] Reversibility confirmed via manual SQL

---

## Backward Compatibility

✅ **Fully Backward Compatible**

- Existing `NULL` active_flag values treated as active
- No changes to database schema
- Dashboard gracefully handles missing status information
- All existing APIs continue to function unchanged
- Existing scripts and cron jobs work without modification

---

## Performance Impact

**Minimal Performance Impact**:

- Closure check: ~1-3 seconds per 100 epics (batched API calls)
- Dashboard generation: +0.5-1 second (database lookups for status)
- Burndown processing: No change (same queries, same processing)
- Database queries: Indexed on `issue_key` (primary key) - fast lookups

**Estimated Runtime**:
- 50 epics: ~2-5 seconds for closure check
- 100 epics: ~5-10 seconds for closure check
- Dashboard with 100 charts: ~2-3 seconds total

---

## Monitoring & Alerts

### Key Log Messages to Monitor

**Success**:
```
[INFO] Successfully closed N initiatives
[INFO] Closed initiatives: COMPDIV-123, COMPDIV-456, ...
```

**No Action Needed**:
```
[INFO] No initiatives need to be closed. All active initiatives are still open
```

**Errors** (require investigation):
```
[ERROR] Failed to close completed initiatives: <error>
[ERROR] Failed to fetch issues for chunk starting at N: <error>
```

### Recommended Cron Schedule

Current setup (already in place):
```cron
# Daily sync includes closure check at 9:00 AM weekdays
0 9 * * 1-5 /path/to/jira_server/run_daily_job.sh
```

No changes to cron schedule required.

---

## Future Enhancements

Potential future improvements (not in this deployment):

1. **Admin UI**: Web interface for manually reopening epics
2. **Notification System**: Alert managers when their epics are auto-closed
3. **Closure History**: Track who closed epic and when (audit log)
4. **Reopening Detection**: Automatically detect epics reopened in Jira
5. **Closure Metrics**: Dashboard showing closure rate trends

---

## Support & Troubleshooting

### Common Issues

**Issue**: Epic closed incorrectly
**Solution**: Use manual reopening SQL (see "Manual Reopening" in CLAUDE.md)

**Issue**: Dashboard not showing completed badges
**Solution**:
1. Check database: `SELECT active_flag, eff_end_date FROM tbl_initiative_issue_keys WHERE issue_key = 'XXX';`
2. Regenerate dashboard: `curl -X POST http://127.0.0.1:8000/jobs/generate-burndown-dashboard`

**Issue**: Closure check not running
**Solution**:
1. Check logs: `tail -f logs/app.log | grep "close completed"`
2. Manually trigger: `curl -X POST http://127.0.0.1:8000/jobs/daily`
3. Verify Jira connectivity: Check for authentication errors in logs

**Issue**: Burndown data missing for closed epic
**Solution**:
- Verify epic key in `tbl_initiative_issue_keys`
- Run burndown manually: `curl -X POST http://127.0.0.1:8000/jobs/compdiv-burndown`
- Check logs for processing errors

### Verification Queries

```sql
-- Summary of epic statuses
SELECT
  CASE
    WHEN active_flag IS NULL THEN 'Active (NULL)'
    WHEN active_flag = true THEN 'Active (TRUE)'
    WHEN active_flag = false THEN 'Closed'
  END as status,
  COUNT(*) as count,
  MIN(eff_end_date) as earliest_closure,
  MAX(eff_end_date) as latest_closure
FROM tbl_initiative_issue_keys
GROUP BY active_flag
ORDER BY active_flag NULLS FIRST;

-- Recently closed epics
SELECT issue_key, eff_end_date, "IRIS"
FROM tbl_initiative_issue_keys
WHERE active_flag = false
  AND eff_end_date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY eff_end_date DESC;

-- Verify burndown data exists for closed epics
SELECT
  i.issue_key,
  i.eff_end_date,
  COUNT(b.run_date) as burndown_records,
  MAX(b.run_date) as latest_burndown
FROM tbl_initiative_issue_keys i
LEFT JOIN tbl_compdiv_burndown b ON i.issue_key = b.epic_key
WHERE i.active_flag = false
GROUP BY i.issue_key, i.eff_end_date
ORDER BY i.eff_end_date DESC;
```

---

## Sign-Off

**Implemented By**: Claude Code (Anthropic)
**Reviewed By**: _________________
**Approved By**: _________________
**Deployment Date**: _________________

---

## Appendix: Technical Details

### Closure Logic Flow

```
1. Daily Job Trigger (/jobs/daily)
   ↓
2. run_jira_export_task() in tasks.py
   ↓
3. close_completed_initiatives(jira, db_pool, None)
   ↓
4. Query: SELECT issue_key WHERE active_flag IS NULL OR true
   ↓
5. For each epic (batches of 100):
   5a. Fetch from Jira: issue.fields.status.statusCategory.name
   5b. If statusCategory == "Done": Add to keys_to_close[]
   ↓
6. UPDATE tbl_initiative_issue_keys
   SET eff_end_date = CURRENT_DATE, active_flag = false
   WHERE issue_key = ANY(keys_to_close)
   ↓
7. Commit transaction
   ↓
8. Log closure results
```

### Dashboard Sorting Logic

```python
# Two-tier sort key
sort_key = lambda chart: (
    not chart.get('is_active', True),  # False (active) sorts first
    chart.get('epic_key', '')           # Then alphabetical A→Z
)

# Result:
# 1. Active epics: COMPDIV-100, COMPDIV-200, COMPDIV-300
# 2. Closed epics: COMPDIV-150, COMPDIV-250
```

### CSS Classes for Completed Epics

```css
.completed-epic {
    color: #c62828;      /* Bold red */
    font-weight: 700;
}

.completed-badge {
    background-color: #ffebee;  /* Light red background */
    border: 1px solid #ef9a9a;
    color: #c62828;
    padding: 2px 6px;
    border-radius: 3px;
}
```

---

**End of Migration Notes**
