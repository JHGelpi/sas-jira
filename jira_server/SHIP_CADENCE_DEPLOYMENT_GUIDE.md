# Ship Cadence Migration - Deployment Guide

**Version**: 1.0
**Date**: 2025-10-28
**Status**: Ready for Deployment

---

## Prerequisites Checklist

Before starting deployment, ensure:

- [ ] You have database owner permissions OR access to someone who does
- [ ] FastAPI server can be temporarily stopped for testing
- [ ] Backup of production database has been taken
- [ ] Access to server logs directory
- [ ] Estimated downtime window: 2-3 hours (non-production impacting)

---

## Deployment Steps

### Step 1: Database Schema Migration

**Who**: Database Admin (requires owner permissions)
**Duration**: ~2 minutes
**Impact**: None (column is nullable)

```bash
# Execute schema migration
psql -U <database_owner> -d jira_data -f schema_migrations/001_add_ship_cadence_column.sql
```

**Expected Output**:
```
NOTICE:  ship_cadence column added successfully
NOTICE:  Index idx_jira_sprint_data_ship_cadence created successfully
```

**Verification**:
```sql
-- Check column exists
SELECT column_name, data_type, character_maximum_length, is_nullable
FROM information_schema.columns
WHERE table_name = 'tbl_jira_sprint_data'
AND column_name = 'ship_cadence';

-- Expected: ship_cadence | character varying | 7 | YES
```

---

### Step 2: Backfill Historical Data

**Who**: Operations/DevOps
**Duration**: ~10-30 minutes (depends on table size)
**Impact**: Database load increase during backfill

```bash
# Navigate to jira_server directory
cd /Users/wegelpi/github_repos/sas-jira/jira_server

# Activate virtual environment
source venv/bin/activate

# DRY RUN first to estimate time
python backfill_ship_cadence.py --dry-run

# Review dry run output, then execute
python backfill_ship_cadence.py --batch-size 10000

# Verify results
python backfill_ship_cadence.py --verify-only
```

**Expected Output**:
```
BACKFILL SUMMARY
================================================================================
Total records in table: 50,000
Records updated: 45,000
Records skipped (already populated): 0
Records with valid ship_cadence: 42,000
Records without valid ship_cadence: 3,000
```

**Verification**:
```sql
-- Check backfill coverage
SELECT
    COUNT(*) as total_records,
    COUNT(ship_cadence) as records_with_ship_cadence,
    ROUND(COUNT(ship_cadence) * 100.0 / COUNT(*), 2) as coverage_pct
FROM tbl_jira_sprint_data;

-- Sample data comparison
SELECT issue_key, fix_version, ship_cadence
FROM tbl_jira_sprint_data
WHERE ship_cadence IS NOT NULL
LIMIT 10;
```

---

### Step 3: Test ETL Pipeline

**Who**: Operations/DevOps
**Duration**: ~5 minutes
**Impact**: None (testing only)

```bash
# Ensure FastAPI server is running
./run_app.sh

# In another terminal, trigger daily job
curl -X POST http://127.0.0.1:8000/jobs/daily

# Check logs for ship_cadence population
tail -f logs/app.log | grep ship_cadence
```

**Verification**:
```sql
-- Check recent records have ship_cadence
SELECT issue_key, fix_version, ship_cadence, export_date
FROM tbl_jira_sprint_data
WHERE export_date >= CURRENT_DATE
ORDER BY export_date DESC
LIMIT 20;
```

---

### Step 4: Update Database Views

**Who**: Database Admin
**Duration**: ~5 minutes
**Impact**: Brief view recreation (milliseconds)

```bash
# Execute view updates
psql -U <database_owner> -d jira_data -f schema_migrations/003_update_views_with_ship_cadence.sql
```

**Expected Output**:
```
CREATE OR REPLACE VIEW
...
NOTICE: View migration completed successfully
NOTICE: All views now have both normalized_sprint and ship_cadence columns
```

**Verification**:
```sql
-- Verify all views have both columns
SELECT
    table_name,
    COUNT(CASE WHEN column_name = 'normalized_sprint' THEN 1 END) AS has_normalized_sprint,
    COUNT(CASE WHEN column_name = 'ship_cadence' THEN 1 END) AS has_ship_cadence
FROM information_schema.columns
WHERE table_name IN ('view_jira_sprint_data', 'view_jira_curr_record', 'view_dedup_investment_flags')
AND column_name IN ('normalized_sprint', 'ship_cadence')
GROUP BY table_name
ORDER BY table_name;

-- Expected: Each view should show (1, 1)
```

---

### Step 5: Deploy Application Code

**Who**: Developer/DevOps
**Duration**: ~2 minutes
**Impact**: Brief server restart

**Files Already Updated** (committed to repository):
- ✅ `jira_data_analysis/jira_utils.py` - normalize_fix_version() function
- ✅ `jira_data_analysis/jira_processor.py` - ETL pipeline updates
- ✅ `jira_data_analysis/okr_summary.sql` - Uses ship_cadence
- ✅ `jira_data_analysis/investment_trends.py` - Uses ship_cadence
- ✅ `jira_automation/data_quality_report.py` - Validation logic

```bash
# If code is not yet committed, commit it now
git add .
git commit -m "Implement ship_cadence migration from normalized_sprint

- Add ship_cadence column to ETL pipeline
- Update okr_summary.sql to use ship_cadence
- Update investment_trends.py charts to use ship_cadence
- Add backfill and migration scripts"

git push origin main

# If already committed, pull latest code on server
cd /Users/wegelpi/github_repos/sas-jira/jira_server
git pull

# Restart FastAPI server
# (Stop current server with Ctrl+C, then)
./run_app.sh
```

---

### Step 6: Test Reports and Dashboards

**Who**: QA/Developer
**Duration**: ~15 minutes
**Impact**: None (testing only)

#### Test 1: Investment Trends Report

```bash
# Trigger investment trends report
curl -X POST http://127.0.0.1:8000/jobs/release

# Check logs
tail -f logs/app.log

# Verify charts were generated
ls -lh /Users/wegelpi/Library/CloudStorage/OneDrive-SAS/__ComputeDiv-Leadership/okr_data/
```

**Verification**:
- Open generated HTML charts in browser
- Verify X-axis shows "Ship Cadence" instead of "Normalized Sprint"
- Verify data looks consistent with previous reports
- Check for any errors in console

#### Test 2: Data Quality Report

```bash
# Trigger data quality report
curl -X POST http://127.0.0.1:8000/jobs/data-quality-report

# Check logs for fix version validation
tail -f logs/app.log | grep ship_cadence
```

#### Test 3: OKR Summary SQL

```sql
-- Run okr_summary.sql manually
-- (Copy content from jira_data_analysis/okr_summary.sql)

-- Verify output has ship_cadence column
SELECT * FROM (...okr_summary query...) LIMIT 10;

-- Compare row counts with previous normalized_sprint results
-- Should be identical
```

---

## Rollback Plan

If issues are discovered during deployment:

### Scenario 1: ETL Issues (Step 2-3)

**Symptoms**: Ship_cadence not being populated correctly

**Action**:
1. Stop FastAPI server
2. Fix jira_processor.py code
3. Re-run backfill script
4. Restart server

**Impact**: No data loss, ETL can continue with fixes

### Scenario 2: View Issues (Step 4)

**Symptoms**: Views throwing errors, missing columns

**Action**:
```bash
# Revert views to original definitions
psql -U <database_owner> -d jira_data -f view_definitions/view_jira_sprint_data_original.sql
psql -U <database_owner> -d jira_data -f view_definitions/view_jira_curr_record_original.sql
psql -U <database_owner> -d jira_data -f view_definitions/view_dedup_investment_flags_original.sql
```

**Impact**: Views revert to normalized_sprint only, application code may error

### Scenario 3: Application Code Issues (Step 5)

**Symptoms**: Reports failing, charts not generating

**Action**:
```bash
# Revert code changes
git revert <commit-hash>
git push origin main

# Redeploy on server
cd /Users/wegelpi/github_repos/sas-jira/jira_server
git pull
./run_app.sh
```

**Impact**: Reverts to normalized_sprint, ship_cadence column remains but unused

### Complete Rollback

**Only if migration must be completely reversed**:

```sql
-- Drop ship_cadence column (NOT RECOMMENDED - data loss)
ALTER TABLE tbl_jira_sprint_data DROP COLUMN ship_cadence;

-- Drop index
DROP INDEX IF EXISTS idx_jira_sprint_data_ship_cadence;
```

**WARNING**: This will delete all ship_cadence data. Only do this if migration is permanently abandoned.

---

## Monitoring

### Post-Deployment Checks (First 24 Hours)

**Every 2 Hours**:
```bash
# Check ETL logs
tail -100 logs/app.log | grep -i error

# Check database for new records
psql -d jira_data -c "SELECT COUNT(*) FROM tbl_jira_sprint_data WHERE export_date >= CURRENT_DATE AND ship_cadence IS NOT NULL;"
```

**Daily**:
```bash
# Run data quality report
curl -X POST http://127.0.0.1:8000/jobs/data-quality-report

# Check for invalid fix versions
# Review Teams notifications
```

### Key Metrics to Track

| Metric | Query | Target |
|--------|-------|--------|
| Ship Cadence Coverage | `SELECT COUNT(ship_cadence) * 100.0 / COUNT(*) FROM tbl_jira_sprint_data` | > 95% |
| Valid Fix Versions (Done Issues) | Data quality report | < 5% flagged |
| Investment Trends Report Success | Check logs after `/jobs/release` | No errors |
| ETL Runtime | Compare avg runtime before/after | < 10% increase |

---

## Success Criteria

Migration is considered successful when:

- [x] ship_cadence column exists in tbl_jira_sprint_data
- [x] Backfill completed with > 90% coverage
- [x] All 3 views include ship_cadence column
- [x] Investment trends charts display correctly
- [x] OKR summary SQL returns expected data
- [x] ETL pipeline populates ship_cadence for new records
- [x] Data quality reports run without errors
- [x] No increase in error logs after 24 hours

---

## Post-Deployment Tasks

### Week 1

- Monitor data quality metrics daily
- Review Teams notifications for fix version issues
- Validate investment trends charts accuracy
- Collect stakeholder feedback

### Week 2-4

- Compare normalized_sprint vs ship_cadence values
- Identify any data quality gaps
- Refine data validation rules if needed
- Prepare documentation updates

### Month 2+

**Optional Future Phase**: Deprecate normalized_sprint
- Once ship_cadence is proven stable and accurate
- Update remaining references to use ship_cadence
- Eventually remove normalized_sprint from views
- Update documentation to reflect ship_cadence as primary field

---

## Support and Escalation

### Common Issues

#### Issue 1: "ship_cadence column does not exist"

**Cause**: Step 1 (schema migration) not completed
**Fix**: Run `schema_migrations/001_add_ship_cadence_column.sql`

#### Issue 2: "Backfill script fails with timeout"

**Cause**: Database connection timeout
**Fix**: Reduce `--batch-size` parameter (e.g., `--batch-size 5000`)

#### Issue 3: "Investment trends charts show no data"

**Cause**: Views not updated OR no ship_cadence data
**Fix**:
1. Verify views have ship_cadence: `SELECT * FROM view_dedup_investment_flags LIMIT 1`
2. Check backfill completed: `SELECT COUNT(ship_cadence) FROM tbl_jira_sprint_data`

#### Issue 4: "ETL failing with CSV column mismatch"

**Cause**: jira_processor.py not updated
**Fix**: Ensure latest code is deployed, restart server

---

## Appendix: Files Reference

### Migration Scripts
- `schema_migrations/001_add_ship_cadence_column.sql` - Add column and index
- `schema_migrations/003_update_views_with_ship_cadence.sql` - Update all views

### Utility Scripts
- `backfill_ship_cadence.py` - Backfill historical data
- `get_view_definitions.py` - Retrieve view definitions
- `find_normalized_sprint_references.py` - Find dependencies

### Updated Application Files
- `jira_data_analysis/jira_processor.py` - ETL pipeline
- `jira_data_analysis/jira_utils.py` - normalize_fix_version()
- `jira_data_analysis/okr_summary.sql` - Investment metrics query
- `jira_data_analysis/investment_trends.py` - Chart generation
- `jira_automation/data_quality_report.py` - Data validation

### Documentation
- `NORMALIZED_SPRINT_MIGRATION_PLAN.md` - Original migration plan
- `SHIP_CADENCE_MIGRATION_CHECKLIST.md` - Detailed checklist
- `SHIP_CADENCE_PROGRESS_REPORT.md` - Progress tracking
- `SHIP_CADENCE_DEPLOYMENT_GUIDE.md` - This document

---

**Document Owner**: Development Team
**Last Updated**: 2025-10-28
**Next Review**: After deployment completion
