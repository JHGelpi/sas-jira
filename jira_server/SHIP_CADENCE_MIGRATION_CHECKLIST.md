# Ship Cadence Migration Checklist

## Database Objects Found Using `normalized_sprint`

### Views (3 total)
1. **view_jira_sprint_data** - Primary view that calculates normalized_sprint from sprint_name
   - Uses: `regexp_replace((a.sprint_name)::text, '.*(\d{4}\.\d{2}).*'::text, '\1'::text) AS normalized_sprint`
   - **Action Required**: Add `ship_cadence` column to view SELECT list

2. **view_jira_curr_record** - References normalized_sprint from view_jira_sprint_data
   - Uses: `a.normalized_sprint`
   - **Action Required**: Update to use `a.ship_cadence`

3. **view_dedup_investment_flags** - Uses normalized_sprint for investment analysis
   - Uses: `regexp_replace((sprint.sprint_name)::text, '.*(\d{4}\.\d{2}).*'::text, '\1'::text) AS normalized_sprint`
   - **Action Required**: Update to use `ship_cadence` from sprint data

### SQL Files (1 total)
1. **jira_data_analysis/okr_summary.sql** (5 references)
   - Line 8: `a.normalized_sprint,` → `a.ship_cadence,`
   - Line 31: `normalized_sprint,` → `ship_cadence,`
   - Line 39: `PARTITION BY normalized_sprint` → `PARTITION BY ship_cadence`
   - Line 48: `normalized_sprint` → `ship_cadence`
   - Line 51: `normalized_sprint,` → `ship_cadence,`

### Python Files (1 total)
1. **jira_data_analysis/investment_trends.py** (5 references)
   - Line 55: Comment mentions `normalized_sprint`
   - Line 56: `if 'normalized_sprint' in df.columns:` → `if 'ship_cadence' in df.columns:`
   - Line 58: `df['sprint_order'] = pd.to_numeric(df['normalized_sprint'], errors='coerce')` → use `df['ship_cadence']`
   - Line 73: `x='normalized_sprint',` → `x='ship_cadence',`
   - Line 77: `labels={'normalized_sprint': 'Normalized Sprint'` → `labels={'ship_cadence': 'Ship Cadence'`
   - Line 95: `x='normalized_sprint',` → `x='ship_cadence',`
   - Line 100: `labels={'normalized_sprint': 'Normalized Sprint'` → `labels={'ship_cadence': 'Ship Cadence'`

## Migration Steps

### ✅ Phase 1: Preparation (Completed)
- [x] Add `normalize_fix_version()` to jira_utils.py
- [x] Create SQL migration script (schema_migrations/001_add_ship_cadence_column.sql)
- [x] Identify all database objects using normalized_sprint

### 🔄 Phase 1: Remaining Tasks
- [ ] Run SQL migration to add ship_cadence column (requires database owner permissions)
- [ ] Create backfill script for existing data

### ⏳ Phase 2: ETL Integration
- [ ] Update jira_processor.py to populate ship_cadence during ETL
- [ ] Update tbl_jira_sprint_data table definition (if there's a CREATE TABLE script)
- [ ] Run backfill script on existing data
- [ ] Verify ship_cadence is populated correctly

### ⏳ Phase 3: Data Quality (Already Implemented)
- [x] normalize_fix_version() function with validation logic
- [x] check_invalid_fix_versions_for_done_issues() in data_quality_report.py
- [x] Bug resolution filtering (exclude non-Fixed/Completed bugs)

### ⏳ Phase 4: Update Database Views
- [ ] Update view_jira_sprint_data to include ship_cadence
- [ ] Update view_jira_curr_record to reference ship_cadence
- [ ] Update view_dedup_investment_flags to use ship_cadence
- [ ] Test all views after updates

### ⏳ Phase 5: Update Application Code
- [ ] Update okr_summary.sql (5 references)
- [ ] Update investment_trends.py (5 references)
- [ ] Test investment trends report generation
- [ ] Verify charts display correctly

## SQL Migration Commands

### 1. Add ship_cadence Column to Table
```sql
-- Run: schema_migrations/001_add_ship_cadence_column.sql
-- This script is idempotent and safe to re-run
```

### 2. Update view_jira_sprint_data
```sql
CREATE OR REPLACE VIEW view_jira_sprint_data AS
SELECT
    -- ... existing columns ...
    regexp_replace((a.sprint_name)::text, '.*(\d{4}\.\d{2}).*'::text, '\1'::text) AS normalized_sprint,
    a.ship_cadence,  -- Add new column
    -- ... rest of columns ...
FROM tbl_jira_sprint_data a
-- ... rest of view definition ...
```

### 3. Update view_jira_curr_record
```sql
CREATE OR REPLACE VIEW view_jira_curr_record AS
SELECT
    -- ... existing columns ...
    a.normalized_sprint,  -- Keep for backward compatibility initially
    a.ship_cadence,       -- Add new column
    -- ... rest of columns ...
FROM view_jira_sprint_data a
-- ... rest of view definition ...
```

### 4. Update view_dedup_investment_flags
```sql
CREATE OR REPLACE VIEW view_dedup_investment_flags AS
SELECT
    -- ... existing columns ...
    regexp_replace((sprint.sprint_name)::text, '.*(\d{4}\.\d{2}).*'::text, '\1'::text) AS normalized_sprint,  -- Keep temporarily
    sprint.ship_cadence,  -- Add new column from join
    -- ... rest of columns ...
FROM view_jira_curr_record a
-- ... rest of view definition ...
```

## Testing Plan

### 1. Unit Tests
- [x] test_normalize_fix_version() (all 12 tests passing)

### 2. Integration Tests
- [ ] Verify ship_cadence populated in tbl_jira_sprint_data
- [ ] Verify views return ship_cadence column
- [ ] Verify okr_summary.sql returns ship_cadence
- [ ] Verify investment_trends.py generates charts with ship_cadence

### 3. Data Quality Tests
- [ ] Compare normalized_sprint vs ship_cadence values
- [ ] Identify any mismatches or data quality issues
- [ ] Verify Done issues have valid ship_cadence values

## Rollback Plan

If issues arise:
1. Views can be reverted to original definitions (keep old SQL backed up)
2. Application code can be reverted to use normalized_sprint
3. ship_cadence column can be kept but unused (no need to drop)
4. Original sprint_name regex logic remains available

## Communication

### To Database Admin
- Request permissions to run schema_migrations/001_add_ship_cadence_column.sql
- Explain need for ship_cadence column and index
- Estimated downtime: < 1 minute for ALTER TABLE

### To Stakeholders
- Ship cadence calculation moving from sprint name to fix version
- More accurate tracking of release schedules
- Data quality improvements for fix version field

## Notes

- The migration can be done gradually (add column first, update code later)
- Both normalized_sprint and ship_cadence can coexist during transition
- Fix version data quality is improving (Phase 3 already deployed)
- No user-facing changes until Phase 5 is complete
