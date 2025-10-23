# Normalized Sprint Migration Plan
**From Sprint Name to Fix Version-Based Calculation**

## Executive Summary

Migrate the `normalized_sprint` calculation from sprint name regex parsing to fix version-based logic. This will provide more accurate sprint tracking and enable validation of fix version data quality.

---

## Current State

### Current Implementation
- **Source Field**: `tbl_jira_sprint_data.sprint_name`
- **Calculation**: SQL regex `regexp_replace(a.sprint_name::text, '.*(\d{4}\.\d{2}).*'::text, '\1'::text)`
- **Example**:
  - Input: "COMPDIV Sprint 2025.09"
  - Output: "2025.09"

### Current Data Flow
```
Jira API (Sprint field)
    ↓
jira_processor.py (parse_sprint_data)
    ↓
tbl_jira_sprint_data.sprint_name
    ↓
SQL Views (regexp_replace on sprint_name)
    ↓
normalized_sprint (derived in queries)
```

### Current Usage
- **investment_trends.py**: Sorting and grouping by normalized sprint for investment analysis
- **okr_summary.sql**: Aggregating story points by normalized sprint
- Various reports and dashboards

---

## Target State

### New Implementation
- **Source Field**: `tbl_jira_sprint_data.fix_version`
- **Storage**: New column `tbl_jira_sprint_data.normalized_sprint` (materialized, not derived)
- **Calculation**: Python function to parse, sort, and select latest valid fix version
- **Validation**: Data quality audit for Done issues with invalid fix versions

### New Data Flow
```
Jira API (fixVersions field)
    ↓
jira_processor.py (parse_fix_version_data → existing)
    ↓
tbl_jira_sprint_data.fix_version (pipe-delimited)
    ↓
NEW: normalize_fix_version() function
    ↓
tbl_jira_sprint_data.normalized_sprint (new column)
    ↓
Reports/Dashboards (use materialized column)
```

---

## Technical Requirements

### 1. Fix Version Parsing Logic

#### Function: `normalize_fix_version(fix_version_str: str) -> str`

**Input**: Pipe-delimited fix version string
- Examples:
  - `"2025.09|2025.10|2026.01"`
  - `"Now"`
  - `"2025.09"`
  - `"Next|2025.12"`
  - `""` (empty)

**Processing Steps**:
1. Split by pipe delimiter (`|`)
2. Filter for versions matching pattern `YYYY.MM` using regex: `^\d{4}\.\d{2}$`
3. Sort valid versions in descending order (treat as `YYYY.MM` floats: `2026.03 > 2025.12`)
4. Return the **latest** (highest) valid version
5. If no valid versions found, return `None` or empty string

**Output**: Latest valid fix version or empty string
- Examples:
  - `"2025.09|2025.10|2026.01"` → `"2026.01"`
  - `"2026.01|2025.09|2025.10"` → `"2026.01"` (sorted)
  - `"Now"` → `""`
  - `"Next|2025.12"` → `"2025.12"`
  - `""` → `""`

#### Edge Cases to Handle
- Multiple versions: `"2025.09|2025.10|2025.11"` → take latest
- Out of order: `"2026.02|2025.11|2026.01"` → sort first, then take latest
- Mixed valid/invalid: `"Now|2025.09|Next"` → filter to `"2025.09"`
- Year boundaries: `"2025.12|2026.01"` → `"2026.01"` is later
- Invalid formats: `"2025.9"`, `"25.09"`, `"2025-09"` → ignore
- Empty/None: `""`, `None` → return `""`

---

### 2. Database Schema Changes

#### Add Column to `tbl_jira_sprint_data`

```sql
-- Add new column for materialized normalized sprint
ALTER TABLE tbl_jira_sprint_data
ADD COLUMN normalized_sprint VARCHAR(7);

-- Add index for performance (frequently used in WHERE/GROUP BY)
CREATE INDEX idx_jira_sprint_data_normalized_sprint
ON tbl_jira_sprint_data(normalized_sprint);

-- Add comment for documentation
COMMENT ON COLUMN tbl_jira_sprint_data.normalized_sprint
IS 'Latest valid fix version in YYYY.MM format, derived from fix_version field';
```

#### Migration Strategy
1. Add column (non-blocking, nullable)
2. Backfill existing data with new logic
3. Update ETL process to populate on insert
4. Validate data quality
5. Update downstream queries to use new column

---

### 3. ETL Process Updates

#### Modify `jira_processor.py`

**Location**: `jira_server/jira_data_analysis/jira_processor.py`

**Current Code** (line ~243):
```python
parse_fix_version_data(fields.fixVersions), parse_component_data(fields.components),
```

**Changes Needed**:
1. Keep `parse_fix_version_data()` as-is (stores raw pipe-delimited string)
2. Add call to new `normalize_fix_version()` function
3. Include `normalized_sprint` in CSV headers and row data

**Pseudo-code**:
```python
# In process_and_load_issues()
fix_version_raw = parse_fix_version_data(fields.fixVersions)
normalized_sprint = normalize_fix_version(fix_version_raw)

# Add to CSV row
row = [
    # ... existing fields ...
    fix_version_raw,  # Keep original
    normalized_sprint,  # New field
    # ... rest of fields ...
]
```

#### Add Function to `jira_utils.py`

**Location**: `jira_server/jira_data_analysis/jira_utils.py`

**New Function**:
```python
import re

def normalize_fix_version(fix_version_str: str) -> str:
    """
    Extracts and returns the latest valid fix version from a pipe-delimited string.

    Valid fix versions match the pattern YYYY.MM (e.g., 2025.09, 2026.01).
    Invalid values like "Now", "Next", "Future" are ignored.

    Args:
        fix_version_str: Pipe-delimited string of fix versions (e.g., "2025.09|2026.01|Now")

    Returns:
        Latest valid fix version in YYYY.MM format, or empty string if none found

    Examples:
        >>> normalize_fix_version("2025.09|2025.10|2026.01")
        "2026.01"
        >>> normalize_fix_version("Now|2025.12")
        "2025.12"
        >>> normalize_fix_version("Now")
        ""
    """
    if not fix_version_str:
        return ""

    # Split by pipe delimiter
    versions = fix_version_str.split('|')

    # Regex pattern for YYYY.MM format
    pattern = re.compile(r'^\d{4}\.\d{2}$')

    # Filter for valid versions
    valid_versions = [v.strip() for v in versions if pattern.match(v.strip())]

    if not valid_versions:
        return ""

    # Sort in descending order (latest first)
    # Sort as floats to handle 2025.12 < 2026.01 correctly
    valid_versions.sort(key=lambda x: float(x), reverse=True)

    return valid_versions[0]
```

**Unit Tests** (add to test suite):
```python
def test_normalize_fix_version():
    assert normalize_fix_version("2025.09|2025.10|2026.01") == "2026.01"
    assert normalize_fix_version("2026.01|2025.09|2025.10") == "2026.01"
    assert normalize_fix_version("Now") == ""
    assert normalize_fix_version("Next|2025.12") == "2025.12"
    assert normalize_fix_version("2025.09") == "2025.09"
    assert normalize_fix_version("") == ""
    assert normalize_fix_version("2025.12|2026.01") == "2026.01"
    assert normalize_fix_version("Future|Now|Next") == ""
```

---

### 4. Data Quality Audit

#### New Validation Rule

**Rule**: Done issues must have valid fix version in YYYY.MM format

**Logic**:
```
IF issue.statusCategory = "Done"
AND normalized_sprint IS NULL OR normalized_sprint = ""
THEN flag as data quality issue
```

**Implementation Location**: `jira_automation/data_quality_report.py`

#### Add to Data Quality Report

**New Check**:
```python
def check_invalid_fix_versions_for_done_issues(jira, db_pool):
    """
    Finds Done issues without valid fix versions (YYYY.MM format).

    Issues in Done status should have at least one fix version matching
    the YYYY.MM pattern. Issues with only "Now", "Next", or "Future" are flagged.
    """
    jql = """
        statusCategory = Done
        AND (
            fixVersion is EMPTY
            OR fixVersion in ("Now", "Next", "Future")
        )
        AND updated >= -30d
    """

    issues = jira.search_issues(jql, maxResults=1000, fields="key,summary,status,fixVersions")

    invalid_issues = []
    for issue in issues:
        fix_versions = parse_fix_version_data(issue.fields.fixVersions)
        normalized = normalize_fix_version(fix_versions)

        if not normalized:  # No valid YYYY.MM version found
            invalid_issues.append({
                'issue_key': issue.key,
                'status': issue.fields.status.name,
                'fix_versions': fix_versions,
                'summary': issue.fields.summary
            })

    return invalid_issues
```

**Alternative: Database-Based Check** (more efficient for large datasets)
```python
def check_invalid_fix_versions_db(db_pool):
    """
    Queries database for Done issues with invalid normalized_sprint.
    More efficient than JQL for large result sets.
    """
    query = """
        SELECT issue_key, issue_status, fix_version, summary
        FROM tbl_jira_sprint_data
        WHERE issue_status IN ('Done', 'Closed', 'Accepted and Close(Q)')
        AND (normalized_sprint IS NULL OR normalized_sprint = '')
        AND update_date >= CURRENT_DATE - INTERVAL '30 days'
        ORDER BY update_date DESC
        LIMIT 1000
    """
    # Execute and return results
```

#### Notification Integration

**Add to Existing Notification System**:
- Use existing `notification_utils.py` if available
- Send to `jira_quality` Teams channel
- Format: Table with issue key, status, fix versions, summary
- Schedule: Include in daily data quality report run

---

## Implementation Plan

### Phase 1: Preparation & Testing (Week 1)

#### Tasks:
1. **Add `normalize_fix_version()` to `jira_utils.py`**
   - Implement function with comprehensive unit tests
   - Test edge cases with sample data
   - Verify sorting logic handles year boundaries correctly

2. **Database Schema Update**
   - Add `normalized_sprint` column to `tbl_jira_sprint_data`
   - Add index for performance
   - Test on development/staging database first

3. **Create Backfill Script**
   ```python
   # backfill_normalized_sprint.py
   # Updates normalized_sprint for all existing records
   # Can be run iteratively in batches for large tables
   ```

4. **Testing**
   - Unit tests for `normalize_fix_version()`
   - Integration tests with sample Jira data
   - Verify sorting: `2025.12` vs `2026.01`
   - Test mixed valid/invalid versions

### Phase 2: ETL Integration (Week 2)

#### Tasks:
1. **Update `jira_processor.py`**
   - Add `normalized_sprint` to CSV headers
   - Call `normalize_fix_version()` during issue processing
   - Add to database insert/update logic

2. **Update Database Load Procedure**
   - Modify COPY command to include new column
   - Update any stored procedures or triggers

3. **Backfill Historical Data**
   - Run backfill script on production database
   - Validate results: check sample of records manually
   - Log statistics: X records updated, Y with valid versions, Z without

4. **Monitor ETL Process**
   - Run daily job and verify new column is populated
   - Check logs for any errors in `normalize_fix_version()`
   - Validate data: compare old regex logic vs new logic for sample records

### Phase 3: Data Quality Audit (Week 3)

#### Tasks:
1. **Add Fix Version Validation to Data Quality Report**
   - Implement `check_invalid_fix_versions_for_done_issues()`
   - Add to `data_quality_report.py` main execution
   - Test notification to Teams channel

2. **Configure Quality Check**
   - Add to daily quality report schedule
   - Set thresholds for alerting (if needed)
   - Document expected results and false positives

3. **Review Initial Results**
   - Run quality check and review flagged issues
   - Identify patterns (teams, projects, issue types)
   - Work with teams to clean up data

### Phase 4: Migration of Downstream Systems (Week 4)

#### Tasks:
1. **Update SQL Queries**
   - Replace `regexp_replace(sprint_name, ...)` with `normalized_sprint` column
   - Update `okr_summary.sql`
   - Update any ad-hoc queries or views

2. **Update Python Code**
   - Verify `investment_trends.py` works with new column
   - Update any other reports/scripts using normalized sprint

3. **Update Documentation**
   - Update CLAUDE.md with new logic
   - Update README.md if needed
   - Document the change for other developers

4. **Validation**
   - Compare reports before/after change
   - Verify investment trends charts look correct
   - Check dashboard displays

### Phase 5: Cleanup & Monitoring (Week 5)

#### Tasks:
1. **Remove Old Logic** (optional, keep for fallback initially)
   - Can keep regex logic as backup for 1-2 sprints
   - Eventually remove to avoid confusion

2. **Performance Monitoring**
   - Check query performance with new column
   - Verify index is being used
   - Monitor ETL runtime

3. **Data Quality Monitoring**
   - Track trends in invalid fix version issues
   - Report metrics to stakeholders
   - Iterate on validation logic if needed

---

## Risk Assessment & Mitigation

### Risk 1: Data Loss or Corruption
**Impact**: High
**Likelihood**: Low
**Mitigation**:
- Test thoroughly on staging database first
- Backup production database before schema changes
- Run backfill script in batches with validation
- Keep old sprint_name column as fallback

### Risk 2: Breaking Downstream Reports
**Impact**: High
**Likelihood**: Medium
**Mitigation**:
- Identify all queries using normalized_sprint before migration
- Test each report after changes
- Keep dual logic temporarily (populate both old and new)
- Gradual rollout: new column first, migrate queries second

### Risk 3: Invalid Fix Version Data
**Impact**: Medium
**Likelihood**: High
**Mitigation**:
- Data quality audit will surface issues
- Work with teams to clean data proactively
- Allow grace period before enforcing validation
- Document valid fix version format in team guidelines

### Risk 4: Performance Degradation
**Impact**: Medium
**Likelihood**: Low
**Mitigation**:
- Add index on normalized_sprint column
- Monitor query performance before/after
- Materialize column (don't compute on-the-fly)
- Optimize backfill script to run in batches

### Risk 5: Sorting Logic Errors
**Impact**: Medium
**Likelihood**: Medium
**Mitigation**:
- Comprehensive unit tests for edge cases
- Manual validation of sorting (2025.12 vs 2026.01)
- Test with real production data samples
- Peer review of sorting logic

---

## Rollback Plan

If issues arise, we can rollback in phases:

### Immediate Rollback (Day 1-7)
- Revert SQL queries to use old `regexp_replace` logic
- New column exists but isn't used
- No data loss

### Partial Rollback (Week 2-3)
- Keep new column but populate using old sprint_name logic temporarily
- Fix issues with `normalize_fix_version()` function
- Re-deploy corrected version

### Full Rollback (Week 4+)
- Drop `normalized_sprint` column
- Revert all code changes
- Continue with old sprint_name-based logic
- Requires full rollback plan execution

---

## Success Criteria

### Functional Requirements ✓
- [ ] `normalized_sprint` column populated for all records
- [ ] Sorting logic correctly handles year boundaries (2025.12 < 2026.01)
- [ ] Multi-version strings parsed correctly (`"A|B|C"` → latest)
- [ ] Invalid versions filtered out (`"Now"`, `"Next"`, `"Future"`)
- [ ] Data quality audit identifies Done issues with invalid fix versions
- [ ] Reports and dashboards show correct data

### Non-Functional Requirements ✓
- [ ] ETL process runtime increase < 10%
- [ ] Query performance maintained or improved
- [ ] Zero data loss or corruption
- [ ] All downstream reports function correctly
- [ ] Documentation updated

### Quality Metrics ✓
- [ ] Unit test coverage > 90% for new function
- [ ] Manual validation: 100 random records checked
- [ ] Data quality audit runs successfully daily
- [ ] < 5% of Done issues flagged for invalid fix versions (after cleanup)

---

## Open Questions & Decisions Needed

### Question 1: What if an issue has NO fix versions?
**Options**:
- A) Set `normalized_sprint` to `NULL`
- B) Set to empty string `""`
- C) Fallback to old sprint_name regex logic
- **Recommendation**: Option A (NULL) - clearest semantic meaning

### Question 2: Should we keep sprint_name-based logic as fallback?
**Options**:
- A) Yes, use if fix_version yields no valid version
- B) No, strictly use fix_version logic
- **Recommendation**: Option B initially, add fallback if too many NULLs

### Question 3: How to handle issues with ONLY "Now"/"Next"/"Future"?
**Context**: Open/In Progress issues often use these placeholders
**Options**:
- A) Set `normalized_sprint` to NULL (not yet scheduled)
- B) Use current sprint as default
- C) Use a special value like "Unscheduled"
- **Recommendation**: Option A for Done issues (flagged), Option C for open issues

### Question 4: What's the grace period for data quality enforcement?
**Options**:
- A) Immediate flagging (start Day 1)
- B) 2-week grace period for teams to clean data
- C) Report only, no enforcement
- **Recommendation**: Option B - 2 weeks warning, then enforce

### Question 5: Should we support multiple normalized sprints?
**Context**: If issue spans multiple fix versions
**Options**:
- A) Store only latest (current plan)
- B) Store all valid versions as array/pipe-delimited
- **Recommendation**: Option A - simpler, matches current usage patterns

---

## Testing Strategy

### Unit Tests
```python
# test_jira_utils.py
def test_normalize_fix_version_single():
    assert normalize_fix_version("2025.09") == "2025.09"

def test_normalize_fix_version_multiple():
    assert normalize_fix_version("2025.09|2025.10|2026.01") == "2026.01"

def test_normalize_fix_version_unsorted():
    assert normalize_fix_version("2026.01|2025.09|2025.10") == "2026.01"

def test_normalize_fix_version_year_boundary():
    assert normalize_fix_version("2025.12|2026.01") == "2026.01"

def test_normalize_fix_version_invalid_only():
    assert normalize_fix_version("Now|Next|Future") == ""

def test_normalize_fix_version_mixed():
    assert normalize_fix_version("Now|2025.12|Next") == "2025.12"

def test_normalize_fix_version_empty():
    assert normalize_fix_version("") == ""
    assert normalize_fix_version(None) == ""

def test_normalize_fix_version_invalid_format():
    # Single digit month
    assert normalize_fix_version("2025.9") == ""
    # Two digit year
    assert normalize_fix_version("25.09") == ""
    # Dash separator
    assert normalize_fix_version("2025-09") == ""
```

### Integration Tests
1. Load sample Jira data with various fix version patterns
2. Run ETL process
3. Verify `normalized_sprint` column populated correctly
4. Compare against expected results

### Regression Tests
1. Run investment trends report before and after
2. Verify data consistency (same issues, same sprints)
3. Check edge cases: issues with no fix versions, multiple fix versions

---

## Dependencies & Prerequisites

### Technical Dependencies
- PostgreSQL 12+ (for ALTER TABLE, CREATE INDEX)
- Python 3.10+ (for regex, string operations)
- Access to production database (for schema changes)
- Jira API access (for data quality checks)

### Team Dependencies
- Database admin approval for schema changes
- Stakeholder approval for report changes
- Communication to teams about new fix version validation

### Data Dependencies
- Historical `fix_version` data must be populated in `tbl_jira_sprint_data`
- Jira `fixVersions` field must be consistently used by teams

---

## Communication Plan

### Week 1: Announcement
**Audience**: All Jira users, product owners, scrum masters
**Message**:
> "We're improving sprint tracking by using fix versions instead of sprint names. Starting [DATE], the system will validate that Done issues have valid fix versions in YYYY.MM format (e.g., 2025.09). Issues with only 'Now', 'Next', or 'Future' will be flagged."

### Week 2: Reminder
**Audience**: Teams with flagged issues
**Message**:
> "Data quality check: X issues in your team are marked Done but have invalid fix versions. Please update before [DATE] to avoid alerts."

### Week 3: Go-Live
**Audience**: All teams
**Message**:
> "Normalized sprint calculation now uses fix versions. Daily quality reports will flag Done issues without valid YYYY.MM fix versions. Reports and dashboards updated."

### Week 4: Follow-up
**Audience**: All teams
**Message**:
> "Data quality improvement: Y% of issues now have valid fix versions (up from X%). Thank you for cleaning up the data!"

---

## Appendix: Code Samples

### Sample Backfill Script

```python
#!/usr/bin/env python3
"""
Backfill normalized_sprint column for existing records.
Run in batches to avoid locking the table.
"""

import os
from dotenv import load_dotenv
from jira_data_analysis import db_utils
from jira_data_analysis.jira_utils import normalize_fix_version

load_dotenv()

def backfill_normalized_sprint(batch_size=10000):
    """Backfill normalized_sprint for all records in batches."""
    pool = db_utils.get_connection_pool()
    conn = pool.getconn()

    try:
        with conn.cursor() as cur:
            # Get total count
            cur.execute("SELECT COUNT(*) FROM tbl_jira_sprint_data")
            total = cur.fetchone()[0]
            print(f"Total records to process: {total}")

            # Process in batches
            offset = 0
            updated = 0

            while offset < total:
                print(f"Processing batch: {offset} to {offset + batch_size}")

                # Fetch batch
                cur.execute("""
                    SELECT id, fix_version
                    FROM tbl_jira_sprint_data
                    ORDER BY id
                    LIMIT %s OFFSET %s
                """, (batch_size, offset))

                batch = cur.fetchall()

                # Update each record
                for record_id, fix_version in batch:
                    normalized = normalize_fix_version(fix_version)

                    cur.execute("""
                        UPDATE tbl_jira_sprint_data
                        SET normalized_sprint = %s
                        WHERE id = %s
                    """, (normalized, record_id))

                    updated += 1

                conn.commit()
                print(f"Updated {updated} records")

                offset += batch_size

            print(f"Backfill complete! Updated {updated} records")

    except Exception as e:
        conn.rollback()
        print(f"Error during backfill: {e}")
        raise
    finally:
        pool.putconn(conn)


if __name__ == "__main__":
    backfill_normalized_sprint()
```

---

## Timeline Summary

| Week | Phase | Key Activities | Deliverables |
|------|-------|----------------|--------------|
| 1 | Preparation | Function dev, schema update, testing | `normalize_fix_version()`, schema changes |
| 2 | ETL Integration | Update processor, backfill data | Updated ETL, backfilled data |
| 3 | Quality Audit | Add validation, configure alerts | Data quality checks active |
| 4 | Migration | Update queries, reports, docs | All systems using new column |
| 5 | Cleanup | Remove old logic, monitor | Production stable, documented |

**Total Duration**: 5 weeks
**Go-Live Date**: End of Week 3 (quality checks), End of Week 4 (full migration)

---

## Approval & Sign-off

| Role | Name | Approval Date | Signature |
|------|------|---------------|-----------|
| Technical Lead | | | |
| Product Owner | | | |
| Database Admin | | | |
| QA Lead | | | |

---

**Document Version**: 1.0
**Last Updated**: 2025-10-22
**Author**: Claude Code
**Status**: DRAFT - Pending Review
