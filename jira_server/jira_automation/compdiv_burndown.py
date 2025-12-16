from __future__ import annotations

#import logging
import math
import os
import re
from datetime import date, timedelta, datetime
from typing import Iterable, Set, Dict, Tuple, List
from time import perf_counter

from dotenv import load_dotenv
from jira import JIRA
import numpy as np
import plotly.graph_objects as go

from jira_data_analysis import db_utils
from jira_automation.burndown_forecast import constrained_linear_forecast

from logging_utils import get_logger

logger = get_logger(__name__)

# ---- Configuration ----
BUG_TYPES: Set[str] = {"Bug", "Defect"}
STORY_TYPES: Set[str] = {"Story"}
TASK_RESEARCH_TYPES: Set[str] = {"Task", "Research"}
ALLOWED_LINK_TYPES: Set[str] = set()  # empty => traverse all link types
MAX_DEPTH_DEFAULT: int = 6
# Safety: cap total nodes visited during BFS to avoid pathological graphs
MAX_BFS_NODES: int = 5000
# HTTP timeout for Jira API calls (seconds)
JIRA_TIMEOUT_SECONDS: int = int(os.getenv("JIRA_TIMEOUT") or 30)

# Status handling — treat only *non-done* issues as remaining work
DONE_NAME_HINTS: Set[str] = {
    "done",
    "closed",
    "resolved",
    "cancelled",
    "won't fix",
    "wont fix",
    "accepted and close(q)",  # project-specific example
}


def _is_done_status(fields) -> bool:
    """Return True if the issue's status should be treated as DONE/closed.
    Prefers Jira's statusCategory when available; otherwise falls back to name hints.
    """
    status = getattr(fields, "status", None)
    if not status:
        return False
    cat = getattr(status, "statusCategory", None)
    key = (getattr(cat, "key", "") or "").lower()
    if key == "done":
        return True
    # Fallback on name matching
    name = (getattr(status, "name", "") or "").strip().lower()
    # normalize different apostrophes
    name = name.replace("’", "'")
    return name in DONE_NAME_HINTS


# ---- Jira helpers (local, cached) ----
_JIRA_CLIENT: JIRA | None = None
_FIELD_CACHE: Dict[str, str] | None = None  # name.lower() -> id (e.g., customfield_10016)
# Cache for Epic -> issues in that epic (objects), to avoid repeated JQL calls per epic during BFS
_EPIC_IN_EPIC_CACHE: Dict[str, List[object]] = {}


def get_client() -> JIRA:
    """Return a cached Jira client using env vars JIRA_URL, JIRA_TOKEN."""
    global _JIRA_CLIENT
    if _JIRA_CLIENT is not None:
        return _JIRA_CLIENT

    # Load .env once lazily
    load_dotenv()
    url = os.getenv("JIRA_URL")
    token = os.getenv("JIRA_TOKEN")
    if not url or not token:
        raise RuntimeError("Jira credentials missing: set JIRA_URL and JIRA_TOKEN in environment or .env")

    _JIRA_CLIENT = JIRA(server=url, token_auth=token, options={"timeout": JIRA_TIMEOUT_SECONDS})
    try:
        info = _JIRA_CLIENT.server_info()
        logger.info("Connected to Jira: %s", info.get("version"))
    except Exception:  # best-effort log
        logger.info("Connected to Jira")
    return _JIRA_CLIENT


def get_field_id(jira: JIRA, name: str) -> str | None:
    """Return the Jira field id for a display name (case-insensitive). Caches across calls."""
    global _FIELD_CACHE
    if _FIELD_CACHE is None:
        # jira.fields() returns list of dicts with 'id' and 'name'
        all_fields = jira.fields()
        _FIELD_CACHE = {str(f.get("name", "")).lower(): str(f.get("id")) for f in all_fields}
    return _FIELD_CACHE.get(name.lower())


def get_epic_display_name(epic_key: str) -> str:
    """Return the Epic's display name using the Jira 'Epic Name' field if available,
    otherwise fall back to the issue Summary. Never returns an empty string.
    """
    jira = get_client()
    epic_name_id = get_field_id(jira, "Epic Name")
    fields_req = "summary" + (("," + epic_name_id) if epic_name_id else "")
    try:
        issue = jira.issue(epic_key, fields=fields_req)
    except Exception:
        logger.exception("Failed to fetch epic for name: %s", epic_key)
        return epic_key
    # Prefer 'Epic Name' if present
    if epic_name_id:
        val = getattr(issue.fields, epic_name_id, None)
        if val:
            return str(val)
    # Fallback to summary
    return str(getattr(issue.fields, "summary", epic_key))


def get_epic_status_info(epic_key: str) -> tuple[bool, str]:
    """Return (is_closed, status_name) for the COMPDIV epic.
    Uses Jira statusCategory when available; falls back to name hints.
    """
    jira = get_client()
    issue = jira.issue(epic_key, fields="status")
    fields = issue.fields
    name = str(getattr(getattr(fields, "status", None), "name", "") or "")
    return _is_done_status(fields), name


def get_epic_status_text(epic_key: str) -> str:
    """Return the epic's status name as display text (empty string if unknown)."""
    try:
        _, name = get_epic_status_info(epic_key)
        return name
    except Exception:
        logger.exception("Failed to fetch epic status for %s", epic_key)
        return ""


# ---- Utils ----

def _numeric_cf_id(cf_id: str | None) -> str | None:
    """Return only the numeric portion of a custom field id for JQL (cf[12345])."""
    if not cf_id:
        return None
    m = re.search(r"(\d+)$", cf_id)
    return m.group(1) if m else None


def _points(fields, story_points_cf: str | None) -> float:
    if not story_points_cf:
        return 0.0
    try:
        val = getattr(fields, story_points_cf, None)
        return float(val or 0)
    except Exception:
        return 0.0


def _fetch_batch_by_keys(jira, keys: List[str], fields_csv: str):
    if not keys:
        return []
    out = []
    BATCH = 200
    for i in range(0, len(keys), BATCH):
        batch = keys[i : i + BATCH]
        quoted = ",".join(f'"{k}"' for k in batch)
        jql = f"key in ({quoted})"
        t0 = perf_counter()
        issues = jira.search_issues(jql, fields=fields_csv, maxResults=1000)
        dt = perf_counter() - t0
        #logger.debug("JQL fetch batch %d..%d (%d keys) -> %d issues (%.2fs)", i, i+len(batch)-1, len(batch), len(issues), dt)
        out.extend(issues)
    return out


def _expand_neighbors(issue) -> List[str]:
    """Return linked keys via issuelinks + parent/children/subtasks."""
    neigh: Set[str] = set()
    f = issue.fields

    parent = getattr(f, "parent", None)
    if parent and getattr(parent, "key", None):
        neigh.add(parent.key)

    for st in getattr(f, "subtasks", None) or []:
        if getattr(st, "key", None):
            neigh.add(st.key)

    for link in getattr(f, "issuelinks", []) or []:
        ltype = getattr(getattr(link, "type", None), "name", None)
        if ALLOWED_LINK_TYPES and ltype not in ALLOWED_LINK_TYPES:
            continue
        tgt = getattr(link, "outwardIssue", None) or getattr(link, "inwardIssue", None)
        if tgt and getattr(tgt, "key", None):
            neigh.add(tgt.key)

    return list(neigh)


def _initial_children_for_epic(jira, epic_key: str, epic_link_cf: str | None, fields_csv: str):
    """Stories/bugs/tasks directly in the Epic via Epic Link. Not cached; use wrapper below."""
    if not epic_link_cf:
        logger.warning("Epic Link custom field not found; initial JQL limited")
        return []
    num = _numeric_cf_id(epic_link_cf)
    if not num:
        logger.warning("Epic Link id not numeric; initial JQL limited")
        return []
    jql = f'cf[{num}] = "{epic_key}"'
    t0 = perf_counter()
    issues = jira.search_issues(jql, fields=fields_csv, maxResults=1000)
    #logger.debug("JQL in-epic %s -> %d issues (%.2fs)", epic_key, len(issues), perf_counter()-t0)
    return issues


# ---- Collection / Aggregation ----

def _get_issues_in_epic_cached(jira, epic_key: str, epic_link_cf: str | None, fields_csv: str) -> List[object]:
    """Cached wrapper around _initial_children_for_epic to prevent repeated JQL for the same epic."""
    if epic_key in _EPIC_IN_EPIC_CACHE:
        return _EPIC_IN_EPIC_CACHE[epic_key]
    issues = _initial_children_for_epic(jira, epic_key, epic_link_cf, fields_csv)
    _EPIC_IN_EPIC_CACHE[epic_key] = issues
    return issues

def _child_linked_keys_from_issue(issue) -> List[str]:
    """Return *children* of the current issue by following only *downward* Parent/Child links
    and including subtasks. We *ignore* all other link types (relates/blocks/etc.) and we do
    not traverse to parents.

    Rules (direction-sensitive using the link labels):
      • If link has an **outwardIssue** and the **outward** label implies *this issue is parent of the other* or
        *this issue has child*, then the outwardIssue is a **child** (include it).
      • If link has an **inwardIssue** and the **inward** label implies *this issue is parent of the other*,
        then the inwardIssue is a **child** (include it).
      • Labels like **"is child of"/"child of"** indicate the *other* is a **parent** — do **not** include.
      • Subtasks are always treated as children.
    """
    def _other_is_child(label: str, direction: str) -> bool:
        s = (label or "").strip().lower().replace("’", "'")
        if not s:
            return False
        # Strong, explicit patterns first
        if "is parent of" in s or "parent of" in s:
            return True
        if "has child" in s or "has children" in s:
            # Normally appears on the **outward** side, but if encountered on inward
            # we still treat the *other* as child conservatively.
            return True
        if "is child of" in s or "child of" in s:
            return False
        # Heuristic fallbacks
        if direction == "outward" and "child" in s:
            # e.g. outward label contains "child" but not "child of": assume other is child
            return True
        # Default: do not treat as child
        return False

    keys: Set[str] = set()
    f = issue.fields

    # Subtasks count as children
    for st in getattr(f, "subtasks", None) or []:
        k = getattr(st, "key", None)
        if k:
            keys.add(k)
            logger.debug("Child link via subtask: %s -> %s", getattr(issue, "key", "?"), k)

    for link in getattr(f, "issuelinks", []) or []:
        ltype = getattr(link, "type", None)
        if not ltype:
            continue

        # Outward side
        if getattr(link, "outwardIssue", None):
            label = getattr(ltype, "outward", "")
            if _other_is_child(label, "outward"):
                k = getattr(link.outwardIssue, "key", None)
                if k:
                    keys.add(k)
                    logger.debug("Child link (outward): %s --[%s]--> %s", getattr(issue, "key", "?"), label, k)

        # Inward side
        if getattr(link, "inwardIssue", None):
            label = getattr(ltype, "inward", "")
            if _other_is_child(label, "inward"):
                k = getattr(link.inwardIssue, "key", None)
                if k:
                    keys.add(k)
                    logger.debug("Child link (inward): %s --[%s]--> %s", getattr(issue, "key", "?"), label, k)

    return list(keys)




def collect_issue_keys_for_epic(epic_key: str, max_depth: int = MAX_DEPTH_DEFAULT) -> List:
    """
    Return the set of issues to count toward COMPDIV burndown for a given epic, defined as:
      • Issues IN the epic (via Epic Link), and
      • All descendants reached by recursively following *child* relationships
        (Parent/Child-style links and Jira subtasks) up to `max_depth` levels,
      • PLUS: whenever a node in the graph is an **Epic**, also include issues IN that epic
        (via Epic Link) in the recursion.
    """
    jira = get_client()
    sp_cf = get_field_id(jira, "Story Points")
    epic_link_cf = get_field_id(jira, "Epic Link")

    # Fields required for recursion + points
    base_fields = ["issuetype", "status", "issuelinks", "subtasks"]
    fields_list = sorted(set(base_fields + ([sp_cf] if sp_cf else [])))
    fields_csv = ",".join(fields_list)

    # (0) Fetch the epic itself for link expansion
    try:
        epic_issue = jira.issue(epic_key, fields="issuetype,issuelinks,subtasks")
    except Exception:
        logger.exception("Failed to fetch epic %s", epic_key)
        return []

    # (1) Direct children via Epic Link
    in_epic = _get_issues_in_epic_cached(jira, epic_key, epic_link_cf, fields_csv)

    # (2) Direct children via Parent/Child links on the epic
    child_keys_lvl0 = _child_linked_keys_from_issue(epic_issue)
    fetched_children_lvl0 = _fetch_batch_by_keys(jira, child_keys_lvl0, fields_csv) if child_keys_lvl0 else []

    # Seed frontier with union of in-epic issues and direct child-linked issues
    issues_by_key: Dict[str, object] = {iss.key: iss for iss in in_epic}
    for iss in fetched_children_lvl0:
        issues_by_key[iss.key] = iss

    visited: Set[str] = {epic_key} | set(issues_by_key.keys())
    frontier: List[object] = list(issues_by_key.values())

    depth = 0
    seen_epics: Set[str] = set([epic_key])
    nodes_budget = MAX_BFS_NODES
    while frontier and depth < max_depth and nodes_budget > 0:
        logger.debug("BFS depth=%d frontier=%d visited=%d budget=%d", depth, len(frontier), len(visited), nodes_budget)
        next_keys: Set[str] = set()
        extra_epic_issues: List[object] = []

        for iss in frontier:
            # follow Parent/Child links
            next_keys.update(_child_linked_keys_from_issue(iss))

            # If this node is an Epic, also pull its in-epic issues
            try:
                itype = (getattr(getattr(iss.fields, "issuetype", None), "name", "") or "").lower()
            except Exception:
                itype = ""
            if itype == "epic" and epic_link_cf and iss.key not in seen_epics:
                seen_epics.add(iss.key)
                for ex in _get_issues_in_epic_cached(jira, iss.key, epic_link_cf, fields_csv) or []:
                    if ex.key not in visited:
                        extra_epic_issues.append(ex)
                        visited.add(ex.key)
                        issues_by_key.setdefault(ex.key, ex)

        # Remove already-visited before fetching by keys
        next_keys -= visited
        if not next_keys and not extra_epic_issues:
            break

        # fetch by keys gathered from child links
        fetched_by_keys = _fetch_batch_by_keys(jira, list(next_keys), fields_csv) if next_keys else []

        # Build next frontier (dedup by key)
        frontier_map: Dict[str, object] = {}
        for obj in fetched_by_keys + extra_epic_issues:
            if obj.key not in visited:
                visited.add(obj.key)
            frontier_map[obj.key] = obj
            issues_by_key.setdefault(obj.key, obj)

        frontier = list(frontier_map.values())
        nodes_budget -= len(frontier)
        depth += 1

    if nodes_budget <= 0:
        logger.warning("BFS node budget exceeded for %s; results truncated (visited=%d)", epic_key, len(visited))

    return list(issues_by_key.values())


def compute_point_totals(
    issues: Iterable,
    sp_cf: str | None,
    *,
    only_open: bool = True,
    trace: bool = False,
    epic_key: str | None = None,
) -> Tuple[float, float, float, float]:
    """Sum story points across issues into bug/story/task_research buckets.

    Parameters
    ----------
    issues : Iterable
        Iterable of Jira issue objects (must include .fields with issuetype/status/Story Points CF).
    sp_cf : str | None
        Field id for "Story Points" (e.g., "customfield_10016"). If None, counts as 0.
    only_open : bool, default True
        If True, exclude issues whose status is in Jira's DONE category (or matches DONE_NAME_HINTS).
    trace : bool, default False
        If True, emit a per-issue trace line for *Story/Bug/Task/Research* items showing whether points were counted.
    epic_key : str | None
        Epic key used in trace logs.
    """
    bug_pts = 0.0
    story_pts = 0.0
    task_research_pts = 0.0

    for iss in issues:
        f = getattr(iss, "fields", None)
        if not f:
            continue
        itype = str(getattr(getattr(f, "issuetype", None), "name", "") or "")
        if itype not in BUG_TYPES and itype not in STORY_TYPES and itype not in TASK_RESEARCH_TYPES:
            # Only trace the three categories we count
            continue

        status_name = str(getattr(getattr(f, "status", None), "name", "") or "")
        pts = _points(f, sp_cf)
        is_done = _is_done_status(f)
        counted = (not only_open) or (not is_done)

        if counted:
            if itype in BUG_TYPES:
                bug_pts += pts
            elif itype in STORY_TYPES:
                story_pts += pts
            elif itype in TASK_RESEARCH_TYPES:
                task_research_pts += pts

        if trace:
            action = "COUNT" if counted else "SKIP_DONE"
            logger.info(
                "[%s] %s type=%s status=%s points=%.2f -> %s",
                epic_key or "?",
                getattr(iss, "key", "?"),
                itype,
                status_name,
                pts,
                action,
            )

    total = bug_pts + story_pts + task_research_pts
    if trace:
        logger.info(
            "%s: TRACE TOTALS -> bug=%.2f story=%.2f task_research=%.2f total=%.2f",
            epic_key or "?",
            bug_pts,
            story_pts,
            task_research_pts,
            total,
        )
    return round(bug_pts, 2), round(story_pts, 2), round(task_research_pts, 2), round(total, 2)


def upsert_burndown_row(run_dt: date, epic_key: str, bug: float, story: float, task_research: float, total: float) -> None:
    pool = db_utils.get_connection_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.tbl_compdiv_burndown (run_date, epic_key, bug_points, story_points, task_research_points, total_points)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (run_date, epic_key)
                DO UPDATE SET bug_points=EXCLUDED.bug_points,
                              story_points=EXCLUDED.story_points,
                              task_research_points=EXCLUDED.task_research_points,
                              total_points=EXCLUDED.total_points;
                """,
                (run_dt, epic_key, bug, story, task_research, total),
            )
        conn.commit()
    finally:
        pool.putconn(conn)


def cleanup_old_compdiv_html_files(active_epic_keys: Set[str]) -> None:
    """Remove HTML files for COMPDIV epics that are no longer being tracked (completed > 30 days ago).

    Args:
        active_epic_keys: Set of epic keys currently being tracked
    """
    load_dotenv()
    base_dir = os.getenv("COMPDIV_BURNDOWN_DIR") or os.path.join("reports", "compdiv_burndown")

    if not os.path.exists(base_dir):
        logger.warning(f"Burndown directory does not exist: {base_dir}")
        return

    # Find all COMPDIV HTML files (excluding IRIS_ prefixed files)
    try:
        all_files = [f for f in os.listdir(base_dir)
                     if f.startswith("COMPDIV") and f.endswith("_burndown.html") and not f.startswith("IRIS_")]
        removed_count = 0

        for filename in all_files:
            # Extract epic key from filename (e.g., COMPDIV-123_burndown.html -> COMPDIV-123)
            match = re.search(r'(COMPDIV-\d+)_burndown\.html', filename)
            if match:
                epic_key = match.group(1)
                if epic_key not in active_epic_keys:
                    # This epic is no longer active (completed > 30 days ago), remove its HTML file
                    filepath = os.path.join(base_dir, filename)
                    os.remove(filepath)
                    logger.info(f"Removed old COMPDIV HTML file: {filename} (epic completed > 30 days ago)")
                    removed_count += 1

        if removed_count > 0:
            logger.success(f"Cleaned up {removed_count} old COMPDIV HTML file(s)")
        else:
            logger.debug("No old COMPDIV HTML files to clean up")

    except Exception as e:
        logger.exception(f"Error during COMPDIV HTML cleanup: {e}")


def run_for_all_compdiv_epics(run_dt: date | None = None, filter_flag: str | None = None) -> Dict[str, Tuple[float, float, float, float]]:
    """Load epic keys from tbl_initiative_issue_keys and compute/store today’s totals for each.
    Optionally filter which COMPDIV epics to run via the new `filter_flag` column.

    Filtering behavior
    ------------------
    • If `filter_flag` param is provided (non-empty), only rows where tbl_initiative_issue_keys.filter_flag = filter_flag are used.
    • If the param is None/empty, we will read COMPDIV_FILTER_FLAG from the environment; if unset, all epics are used.
    • The column is CHAR(7) and optional; equality works fine even with CHAR padding in Postgres.

    Emits a clear completion log when finished.
    """
    t_start = perf_counter()
    run_dt = run_dt or date.today()

    # Resolve filter flag from param or environment
    if not filter_flag:
        load_dotenv()
        ff = os.getenv("COMPDIV_FILTER_FLAG", "").strip()
        filter_flag = ff or None

    # Load candidate epics (optionally filtered)
    # *** DATA SAFETY ***
    # This query includes:
    # - Active epics (active_flag IS NULL OR active_flag = true)
    # - Recently completed epics (active_flag = false AND eff_end_date >= CURRENT_DATE - INTERVAL '30 days')
    # Epics completed more than 30 days ago are excluded to keep the dashboard focused.
    pool = db_utils.get_connection_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            params: List[object] = []
            if filter_flag:
                base_sql = (
                    """
                    SELECT DISTINCT issue_key
                    FROM public.tbl_initiative_issue_keys
                    WHERE (
                        active_flag IS NULL
                        OR active_flag = true
                        OR (active_flag = false AND eff_end_date >= CURRENT_DATE - INTERVAL '30 days')
                      )
                      AND filter_flag = %s
                    """
                )
                params.append(filter_flag)
            else:
                base_sql = (
                    """
                    SELECT DISTINCT issue_key
                    FROM public.tbl_initiative_issue_keys
                    WHERE issue_key ~ '^COMPDIV-\d+$'
                      AND (
                        active_flag IS NULL
                        OR active_flag = true
                        OR (active_flag = false AND eff_end_date >= CURRENT_DATE - INTERVAL '30 days')
                      )
                    """
                )
            cur.execute(base_sql, params)
            epic_keys = [r[0] for r in cur.fetchall()]
    finally:
        pool.putconn(conn)

    jira = get_client()
    sp_cf = get_field_id(jira, "Story Points")

    results: Dict[str, Tuple[float, float, float, float]] = {}
    successes = 0
    failures = 0

    for epic in epic_keys:
        try:
            # Check epic status for logging purposes (but process regardless of status for historical data)
            is_closed, epic_status_name = get_epic_status_info(epic)
            status_label = "CLOSED" if is_closed else "ACTIVE"
            logger.info("COMPDIV burndown start: %s (status: %s - %s)", epic, status_label, epic_status_name)

            issues = collect_issue_keys_for_epic(epic, MAX_DEPTH_DEFAULT)
            #logger.info("Collected %d issues for %s", len(issues), epic)

            trace_flag = _should_trace(epic)
            bug, story, task_research, total = compute_point_totals(
                issues, sp_cf, only_open=True, trace=trace_flag, epic_key=epic
            )
            upsert_burndown_row(run_dt, epic, bug, story, task_research, total)
            results[epic] = (bug, story, task_research, total)
            successes += 1
            '''
            logger.info(
                "COMPDIV burndown done: %s (bug=%.2f story=%.2f task_research=%.2f total=%.2f)",
                epic,
                bug,
                story,
                task_research,
                total,
            )
            '''
            # Write/overwrite the HTML chart file for this epic (unless COMPDIV_SKIP_HTML is set)
            try:
                load_dotenv()
                skip_html = os.getenv("COMPDIV_SKIP_HTML", "").strip().lower() in {"1","true","yes","y"}
                if not skip_html:
                    path = write_plot_html(epic)
                    #logger.info("Wrote burndown HTML: %s", path)
            except Exception:
                logger.exception("Failed to write HTML chart for %s", epic)
        except Exception:
            failures += 1
            logger.exception("Failed burndown for %s", epic)

    duration = perf_counter() - t_start

    # Clean up HTML files for epics no longer being tracked (completed > 30 days ago)
    try:
        cleanup_old_compdiv_html_files(set(epic_keys))
    except Exception:
        logger.exception("Failed to clean up old COMPDIV HTML files")

    # Final, explicit completion confirmation
    logger.info(
        "COMPDIV burndown completed successfully. run_date=%s, epics_total=%d, successes=%d, failures=%d, duration=%.2fs",
        run_dt, len(results) + failures, successes, failures, duration,
    )
    return results


def _should_trace(epic_key: str) -> bool:
    """Return True if the current epic should emit per-issue trace logs.
    Controlled via env var COMPDIV_TRACE. Examples:
      COMPDIV_TRACE="*"                  -> trace all epics
      COMPDIV_TRACE="COMPDIV-72"         -> trace just 72
      COMPDIV_TRACE="COMPDIV-72,COMPDIV-45" -> trace a list
    """
    load_dotenv()
    spec = os.getenv("COMPDIV_TRACE", "").strip()
    if not spec:
        return False
    if spec == "*":
        return True
    targets = {s.strip() for s in spec.split(",") if s.strip()}
    return epic_key in targets


# ---- Prediction + chart ----

def _linear_zero_day_with_ci(dates: List[date], totals: List[float], conf: float = 0.80):
    """
    Wrapper for shared constrained forecast logic with COMPDIV-specific config.

    Uses constrained linear regression with 365-day maximum completion horizon.
    If the natural burndown slope is too shallow (would predict completion > 365 days),
    returns (None, None, None) instead of showing an unrealistic forecast.

    Parameters
    ----------
    dates : List[date]
        Observation dates (must be sorted chronologically)
    totals : List[float]
        Points remaining at each date
    conf : float, default 0.80
        Confidence level for CI (0.80 = 80%)

    Returns
    -------
    Tuple[Optional[date], Optional[date], Optional[date]]
        (zero_date, ci_lower, ci_upper)
        - All dates are None if no valid forecast can be made

    Notes
    -----
    Respects COMPDIV_MAX_LOOKAHEAD_DAYS environment variable for optional
    horizon limiting (0 = disabled).
    """
    load_dotenv()
    try:
        max_look = int(os.getenv("COMPDIV_MAX_LOOKAHEAD_DAYS") or 0)
    except Exception:
        max_look = 0

    return constrained_linear_forecast(dates, totals, conf=conf, max_lookahead_days=max_look)


def fetch_burndown_series(epic_key: str) -> Tuple[List[date], List[float], List[float], List[float], List[float]]:
    pool = db_utils.get_connection_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT run_date, bug_points, story_points, task_research_points, total_points
                FROM public.tbl_compdiv_burndown
                WHERE epic_key = %s
                ORDER BY run_date ASC
                """,
                (epic_key,),
            )
            rows = cur.fetchall()
    finally:
        pool.putconn(conn)

    dates = [r[0] for r in rows]
    bug = [float(r[1]) for r in rows]
    story = [float(r[2]) for r in rows]
    task_research = [float(r[3]) for r in rows]
    total = [float(r[4]) for r in rows]
    return dates, bug, story, task_research, total


def build_plot_html(epic_key: str) -> str:
    dates, bug, story, task_research, total = fetch_burndown_series(epic_key)
    epic_title = get_epic_display_name(epic_key)
    status_name = get_epic_status_text(epic_key)

    # Normalize all x-values to datetime for Plotly shapes/annotations
    def _to_dt(d):
        if isinstance(d, datetime):
            return d
        if isinstance(d, date):
            return datetime(d.year, d.month, d.day)
        return d

    dt_dates = [_to_dt(d) for d in dates]

    # Filter historical data to last 3 months for visualization
    # Keep full data for regression calculations (for accuracy)
    three_months_ago = date.today() - timedelta(days=90)
    filtered_indices = [i for i, d in enumerate(dates) if d >= three_months_ago]

    if filtered_indices:
        # Create filtered versions for display
        filtered_dates = [dates[i] for i in filtered_indices]
        filtered_dt_dates = [dt_dates[i] for i in filtered_indices]
        filtered_bug = [bug[i] for i in filtered_indices]
        filtered_story = [story[i] for i in filtered_indices]
        filtered_task_research = [task_research[i] for i in filtered_indices]
        filtered_total = [total[i] for i in filtered_indices]
    else:
        # If no data in last 3 months, use all data as fallback
        filtered_dates = dates
        filtered_dt_dates = dt_dates
        filtered_bug = bug
        filtered_story = story
        filtered_task_research = task_research
        filtered_total = total

    fig = go.Figure()
    if filtered_dt_dates:
        fig.add_trace(go.Scatter(x=filtered_dt_dates, y=filtered_total, mode="lines+markers", name="Total points"))
        fig.add_trace(go.Scatter(x=filtered_dt_dates, y=filtered_bug, mode="lines+markers", name="Bug points"))
        fig.add_trace(go.Scatter(x=filtered_dt_dates, y=filtered_story, mode="lines+markers", name="Story points"))
        fig.add_trace(go.Scatter(x=filtered_dt_dates, y=filtered_task_research, mode="lines+markers", name="Task/Research points"))

        # Add regression trend line if we have enough data
        if len(dates) >= 3 and len(total) >= 3:
            # Calculate OLS regression for visualization
            t0 = min(dates)
            t = np.array([(d - t0).days for d in dates], dtype=float)
            y = np.array(total, dtype=float)

            try:
                X = np.column_stack([np.ones_like(t), t])
                beta = np.linalg.inv(X.T @ X) @ (X.T @ y)
                a, b = float(beta[0]), float(beta[1])

                # Only draw trend line if slope is negative (actually burning down)
                if b < 0 and abs(b) >= 1e-6:
                    # Check if it passes the 365-day constraint
                    b_min = -a / 365
                    passes_constraint = (b <= b_min)

                    # Extend trend line from start to zero-crossing (or reasonable endpoint)
                    t_zero = -a / b

                    # For valid forecasts: extend to zero; for slow forecasts: limit extension
                    if passes_constraint:
                        t_end = t_zero  # Extend all the way to zero
                    else:
                        t_end = max(t) + 90  # Extend only 90 days beyond last data point

                    # Generate trend line points
                    t_trend = np.array([0, t_end])
                    y_trend = a + b * t_trend
                    dates_trend = [t0 + timedelta(days=float(ti)) for ti in t_trend]
                    dt_dates_trend = [_to_dt(d) for d in dates_trend]

                    # Style based on constraint
                    if passes_constraint:
                        line_style = dict(color='green', dash='dash', width=2)
                        trend_name = "Trend line (forecast valid)"
                    else:
                        line_style = dict(color='red', dash='dot', width=2)
                        trend_name = "Trend line (too slow, >365 days)"

                    fig.add_trace(go.Scatter(
                        x=dt_dates_trend,
                        y=y_trend,
                        mode="lines",
                        name=trend_name,
                        line=line_style,
                        hovertemplate='Trend: %{y:.1f} points<extra></extra>'
                    ))
            except (np.linalg.LinAlgError, ValueError):
                pass  # Skip trend line if regression fails

        zdt, lo, hi = _linear_zero_day_with_ci(dates, total, conf=0.80)
        if zdt:
            zdt_dt = _to_dt(zdt)
            fig.add_vline(x=zdt_dt, line_dash="dash")  # avoid built-in annotation bug with date + int
            # Add a separate annotation at the top of the plot area
            fig.add_annotation(
                x=zdt_dt,
                y=1,
                xref="x",
                yref="paper",
                text=f"Zero @ {zdt_dt:%Y-%m-%d}",
                showarrow=False,
                xanchor="left",
                yanchor="bottom",
            )

    # Adjust x-axis range based on forecast scenario
    if filtered_dt_dates:
        last_data_date = max(dates)  # Use original dates for forecast calculations
        x_axis_start = min(filtered_dates)  # Use filtered dates for chart start
        x_axis_end = None

        # Determine appropriate x-axis end date
        if len(dates) >= 3 and len(total) >= 3:
            try:
                # Calculate OLS to determine forecast scenario (using full data for accuracy)
                t0 = min(dates)
                t = np.array([(d - t0).days for d in dates], dtype=float)
                y = np.array(total, dtype=float)
                X = np.column_stack([np.ones_like(t), t])
                beta = np.linalg.inv(X.T @ X) @ (X.T @ y)
                a, b = float(beta[0]), float(beta[1])

                if b < 0 and abs(b) >= 1e-6:
                    # Negative slope (burning down)
                    b_min = -a / 365
                    t_zero = -a / b
                    zero_date = t0 + timedelta(days=t_zero)

                    if b <= b_min:
                        # Valid forecast: extend x-axis to zero date
                        x_axis_end = _to_dt(zero_date)
                    else:
                        # Too slow (>365 days): extend only 3 months beyond last data
                        x_axis_end = _to_dt(last_data_date + timedelta(days=90))
                else:
                    # Positive or flat slope: use default (3 months beyond last data)
                    x_axis_end = _to_dt(last_data_date + timedelta(days=90))
            except (np.linalg.LinAlgError, ValueError, OverflowError):
                # Calculation failed: use default
                x_axis_end = _to_dt(last_data_date + timedelta(days=90))

        if x_axis_end:
            fig.update_xaxes(range=[_to_dt(x_axis_start), x_axis_end])

    # Add clickable title as annotation (Plotly titles don't support links in the title itself)
    # But we'll add both: a standard title for display AND a clickable annotation
    jira_url = f"https://rndjira.sas.com/browse/{epic_key}"
    clickable_title_text = f'<a href="{jira_url}" style="color: #1f77b4; text-decoration: none; font-size: 14px;">[Click to view in Jira: {epic_key}]</a>'

    # Add clickable link annotation below the main title

    #fig.add_annotation(
    #    text=clickable_title_text,
    #    xref="paper",
    #    yref="paper",
    #    x=0.5,
    #    y=1.02,  # Position just below the main title
    #    xanchor="center",
    #    yanchor="bottom",
    #    showarrow=False,
    #    font=dict(size=12),
    #)

    # Set the main chart title (displayed on the chart)
    jira_url = f"https://rndjira.sas.com/browse/{epic_key}"
    chart_title = f"{epic_key}<br>{epic_title}<br><sup>[{status_name}]</sup>"
    clickable_title_text = f'<a href="{jira_url}" style="color: #1f77b4; text-decoration: none; font-size: 14px;">{chart_title}</a>'

    fig.update_layout(
        title=clickable_title_text,
        xaxis_title="Run Date",
        yaxis_title="Points",
        hovermode="x unified",
        template="plotly_white",
        margin=dict(t=100),  # Add top margin for title and annotation
    )

    import plotly.io as pio
    html = pio.to_html(fig, full_html=True, include_plotlyjs="cdn")

    # Set the page title (browser tab title)
    #page_title = f"Burndown chart for {epic_title}"
    page_title = f"Burndown chart for {clickable_title_text}"
    # Replace the default Plotly title with our custom title
    html = html.replace('<head><meta charset="utf-8" /></head>',
                       f'<head><meta charset="utf-8" /><title>{page_title}</title></head>')

    return html


def write_plot_html(epic_key: str, out_dir: str | None = None) -> str:
    """Write/overwrite a single HTML file for an epic in COMPDIV_BURNDOWN_DIR (or default dir).
    File name: COMPDIV123_burndown.html
    Returns the path written.
    """
    # Allow .env override
    load_dotenv()
    base_dir = out_dir or os.getenv("COMPDIV_BURNDOWN_DIR") or os.path.join("reports", "compdiv_burndown")
    os.makedirs(base_dir, exist_ok=True)
    html = build_plot_html(epic_key)
    path = os.path.join(base_dir, f"{epic_key}_burndown.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


__all__ = [
    "collect_issue_keys_for_epic",
    "compute_point_totals",
    "run_for_all_compdiv_epics",
    "fetch_burndown_series",
    "build_plot_html",
    "get_epic_display_name",
    "write_plot_html",
]