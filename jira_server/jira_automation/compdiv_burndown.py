from __future__ import annotations

import logging
import math
import os
import re
from datetime import date, timedelta
from typing import Iterable, Set, Dict, Tuple, List
from time import perf_counter

from dotenv import load_dotenv
from jira import JIRA
import numpy as np
import plotly.graph_objects as go

from jira_data_analysis import db_utils

logger = logging.getLogger(__name__)

# ---- Configuration ----
BUG_TYPES: Set[str] = {"Bug", "Defect"}
STORY_TYPES: Set[str] = {"Story"}  # Add "Task" here if desired
ALLOWED_LINK_TYPES: Set[str] = set()  # empty => traverse all link types
MAX_DEPTH_DEFAULT: int = 6

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

    _JIRA_CLIENT = JIRA(server=url, token_auth=token)
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
        # Quote keys to be safe in JQL
        quoted = ",".join(f'"{k}"' for k in batch)
        jql = f"key in ({quoted})"
        issues = jira.search_issues(jql, fields=fields_csv, maxResults=1000)
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
    """Stories/bugs/tasks directly in the Epic via Epic Link."""
    if not epic_link_cf:
        logger.warning("Epic Link custom field not found; initial JQL limited")
        return []
    num = _numeric_cf_id(epic_link_cf)
    if not num:
        logger.warning("Epic Link id not numeric; initial JQL limited")
        return []
    jql = f'cf[{num}] = "{epic_key}"'
    return jira.search_issues(jql, fields=fields_csv, maxResults=1000)


# ---- Collection / Aggregation ----

def _child_linked_keys_from_issue(issue) -> List[str]:
    """Return keys of *children* for a given issue via Parent/Child-style links
    (and include Jira subtasks as children). Direction rules:
      - If link.outward label contains 'parent' ⇒ outwardIssue is a child
      - If link.inward  label contains 'child'  ⇒ inwardIssue  is a child
      - Fallback: if the link type name mentions parent/child, take the other side
    """
    keys: Set[str] = set()
    f = issue.fields

    # Subtasks count as children
    for st in getattr(f, "subtasks", None) or []:
        if getattr(st, "key", None):
            keys.add(st.key)

    for link in getattr(f, "issuelinks", []) or []:
        ltype = getattr(link, "type", None)
        if not ltype:
            continue
        inward = (getattr(ltype, "inward", "") or "").lower()
        outward = (getattr(ltype, "outward", "") or "").lower()
        name = (getattr(ltype, "name", "") or "").lower()

        # Current issue "is parent of" ⇒ outwardIssue is the child
        if "parent" in outward and getattr(link, "outwardIssue", None):
            k = getattr(link.outwardIssue, "key", None)
            if k:
                keys.add(k)
            continue
        # Current issue "has child" ⇒ inwardIssue is the child
        if "child" in inward and getattr(link, "inwardIssue", None):
            k = getattr(link.inwardIssue, "key", None)
            if k:
                keys.add(k)
            continue
        # Fallback on imprecise names (e.g., type name contains 'Parent/Child')
        if ("parent" in name) or ("child" in name):
            tgt = getattr(link, "outwardIssue", None) or getattr(link, "inwardIssue", None)
            if tgt and getattr(tgt, "key", None):
                keys.add(tgt.key)
    return list(keys)



def collect_issue_keys_for_epic(epic_key: str, max_depth: int = MAX_DEPTH_DEFAULT) -> List:
    """
    Return the set of issues to count toward COMPDIV burndown for a given epic, defined as:
      • Issues IN the epic (via Epic Link), and
      • All descendants reached by recursively following *child* relationships
        (Parent/Child-style links and Jira subtasks) up to `max_depth` levels.
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
        epic_issue = jira.issue(epic_key, fields="issuelinks,subtasks")
    except Exception:
        logger.exception("Failed to fetch epic %s", epic_key)
        return []

    # (1) Direct children via Epic Link
    in_epic = _initial_children_for_epic(jira, epic_key, epic_link_cf, fields_csv)

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
    while frontier and depth < max_depth:
        next_keys: Set[str] = set()
        for iss in frontier:
            next_keys.update(_child_linked_keys_from_issue(iss))
        next_keys -= visited
        if not next_keys:
            break
        next_issues = _fetch_batch_by_keys(jira, list(next_keys), fields_csv)
        frontier = []
        for iss in next_issues:
            if iss.key not in issues_by_key:
                issues_by_key[iss.key] = iss
            visited.add(iss.key)
            frontier.append(iss)
        depth += 1

    return list(issues_by_key.values())


def compute_point_totals(issues: Iterable, sp_cf: str | None, *, only_open: bool = True) -> Tuple[float, float, float]:
    """Sum story points across issues into bug/story buckets.

    Parameters
    ----------
    issues : Iterable
        Iterable of Jira issue objects (must include .fields with issuetype/status/Story Points CF).
    sp_cf : str | None
        Field id for "Story Points" (e.g., "customfield_10016"). If None, counts as 0.
    only_open : bool, default True
        If True, exclude issues whose status is in Jira's DONE category (or matches DONE_NAME_HINTS).
    """
    bug_pts = 0.0
    story_pts = 0.0
    for iss in issues:
        f = iss.fields
        if only_open and _is_done_status(f):
            continue
        itype = getattr(getattr(f, "issuetype", None), "name", "")
        pts = _points(f, sp_cf)
        if itype in BUG_TYPES:
            bug_pts += pts
        elif itype in STORY_TYPES:
            story_pts += pts
        # else: ignore for now
    total = bug_pts + story_pts
    return round(bug_pts, 2), round(story_pts, 2), round(total, 2)


def upsert_burndown_row(run_dt: date, epic_key: str, bug: float, story: float, total: float) -> None:
    pool = db_utils.get_connection_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.tbl_compdiv_burndown (run_date, epic_key, bug_points, story_points, total_points)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (run_date, epic_key)
                DO UPDATE SET bug_points=EXCLUDED.bug_points,
                              story_points=EXCLUDED.story_points,
                              total_points=EXCLUDED.total_points;
                """,
                (run_dt, epic_key, bug, story, total),
            )
        conn.commit()
    finally:
        pool.putconn(conn)


def run_for_all_compdiv_epics(run_dt: date | None = None) -> Dict[str, Tuple[float, float, float]]:
    """Load epic keys from tbl_initiative_issue_keys and compute/store today’s totals for each.
    Emits a clear completion log when finished.
    """
    t_start = perf_counter()
    run_dt = run_dt or date.today()

    # Load candidate epics
    pool = db_utils.get_connection_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT issue_key
                FROM public.tbl_initiative_issue_keys
                WHERE issue_key ~ '^COMPDIV-\d+$'
                """
            )
            epic_keys = [r[0] for r in cur.fetchall()]
    finally:
        pool.putconn(conn)

    jira = get_client()
    sp_cf = get_field_id(jira, "Story Points")

    results: Dict[str, Tuple[float, float, float]] = {}
    successes = 0
    failures = 0

    for epic in epic_keys:
        try:
            logger.info("COMPDIV burndown start: %s", epic)
            issues = collect_issue_keys_for_epic(epic, MAX_DEPTH_DEFAULT)
            logger.info("Seeds for %s: in_epic=%d, child_links=%d", epic, len([i for i in issues if True]), 0)  # legacy msg shape
            logger.info("Collected %d issues for %s", len(issues), epic)

            bug, story, total = compute_point_totals(issues, sp_cf)
            upsert_burndown_row(run_dt, epic, bug, story, total)
            results[epic] = (bug, story, total)
            successes += 1
            logger.info("COMPDIV burndown done: %s (bug=%.2f story=%.2f total=%.2f)", epic, bug, story, total)
        except Exception:
            failures += 1
            logger.exception("Failed burndown for %s", epic)

    duration = perf_counter() - t_start
    # Final, explicit completion confirmation
    logger.info(
        "COMPDIV burndown completed successfully. run_date=%s, epics_total=%d, successes=%d, failures=%d, duration=%.2fs",
        run_dt, len(results) + failures, successes, failures, duration,
    )
    return results


# ---- Prediction + chart ----

def _linear_zero_day_with_ci(dates: List[date], totals: List[float], conf: float = 0.80):
    """Fit y = a + b t ; return t0 date and [lo, hi] (80% CI) when y=0 via delta method."""
    if len(dates) < 3:
        return (None, None, None)
    t0 = min(dates)
    t = np.array([(d - t0).days for d in dates], dtype=float)
    y = np.array(totals, dtype=float)

    X = np.column_stack([np.ones_like(t), t])
    XtX = X.T @ X
    try:
        beta = np.linalg.inv(XtX) @ (X.T @ y)
    except np.linalg.LinAlgError:
        return (None, None, None)

    a, b = float(beta[0]), float(beta[1])
    yhat = X @ beta
    resid = y - yhat
    dof = max(1, len(y) - 2)
    sigma2 = float((resid @ resid) / dof)
    cov_beta = sigma2 * np.linalg.inv(XtX)

    if b >= 0:
        return (None, None, None)  # not burning down

    t_zero = -a / b

    # Delta method for Var(t_zero)
    da = -1.0 / b
    db = a / (b * b)
    var_t0 = (da * da) * cov_beta[0, 0] + (db * db) * cov_beta[1, 1] + 2 * da * db * cov_beta[0, 1]
    se_t0 = math.sqrt(max(0.0, var_t0))

    # z for central 80%
    z = 1.2815515655446004
    lo = t_zero - z * se_t0
    hi = t_zero + z * se_t0

    def clamp_to_dates(x):
        x = max(float(x), 0.0)
        return t0 + timedelta(days=x)

    return (clamp_to_dates(t_zero), clamp_to_dates(lo), clamp_to_dates(hi))


def fetch_burndown_series(epic_key: str) -> Tuple[List[date], List[float], List[float], List[float]]:
    pool = db_utils.get_connection_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT run_date, bug_points, story_points, total_points
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
    total = [float(r[3]) for r in rows]
    return dates, bug, story, total


def build_plot_html(epic_key: str) -> str:
    dates, bug, story, total = fetch_burndown_series(epic_key)
    fig = go.Figure()
    if dates:
        fig.add_trace(go.Scatter(x=dates, y=total, mode="lines+markers", name="Total points"))
        fig.add_trace(go.Scatter(x=dates, y=bug, mode="lines+markers", name="Bug points"))
        fig.add_trace(go.Scatter(x=dates, y=story, mode="lines+markers", name="Story points"))

        zdt, lo, hi = _linear_zero_day_with_ci(dates, total, conf=0.80)
        if zdt:
            fig.add_vline(x=zdt, line_dash="dash", annotation_text=f"Zero @ {zdt:%Y-%m-%d}", annotation_position="top right")
            if lo and hi:
                fig.add_vrect(x0=lo, x1=hi, line_width=0, fillcolor="LightSalmon", opacity=0.2,
                              annotation_text="80% CI", annotation_position="top left")

    fig.update_layout(
        title=f"COMPDIV Burndown: {epic_key}",
        xaxis_title="Run Date",
        yaxis_title="Points",
        hovermode="x unified",
        template="plotly_white",
    )

    import plotly.io as pio
    return pio.to_html(fig, full_html=True, include_plotlyjs="cdn")


__all__ = [
    "collect_issue_keys_for_epic",
    "compute_point_totals",
    "run_for_all_compdiv_epics",
    "fetch_burndown_series",
    "build_plot_html",
]
