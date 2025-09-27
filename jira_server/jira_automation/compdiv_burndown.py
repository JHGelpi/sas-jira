from __future__ import annotations
import math
import logging
from datetime import date, datetime, timedelta
from typing import Iterable, Set, Dict, Tuple, List

import numpy as np
import plotly.graph_objects as go

from jira_automation.jira_client import get_client, get_field_id  # you already have these
from jira_data_analysis import db_utils  # your existing PG pool/helpers

logger = logging.getLogger(__name__)

# Which issue types count toward which buckets
BUG_TYPES = {"Bug", "Defect"}
STORY_TYPES = {"Story"}  # keep tasks/tech-debt out unless you decide otherwise

# Link types to traverse (we’ll traverse anything if empty)
ALLOWED_LINK_TYPES: Set[str] = set()  # empty = allow all

MAX_DEPTH_DEFAULT = 6

def _points(fields, story_points_cf: str | None) -> float:
    if not story_points_cf:
        return 0.0
    val = getattr(fields, story_points_cf, None)
    try:
        return float(val or 0)
    except Exception:
        return 0.0

def _fetch_batch_by_keys(jira, keys: List[str], fields_csv: str):
    if not keys:
        return []
    # Use JQL with batching (Jira caps IN lists; keep batches small)
    out = []
    BATCH = 200
    for i in range(0, len(keys), BATCH):
        batch = keys[i:i+BATCH]
        jql = f'key in ({",".join(f"{k}" for k in batch)})'
        issues = jira.search_issues(jql, fields=fields_csv, maxResults=1000)
        out.extend(issues)
    return out

def _expand_neighbors(issue) -> List[str]:
    """Return linked keys via issuelinks + parent/children/subtasks."""
    neigh: Set[str] = set()
    f = issue.fields

    # Parent/child (subtasks)
    parent = getattr(f, "parent", None)
    if parent and getattr(parent, "key", None):
        neigh.add(parent.key)

    subtasks = getattr(f, "subtasks", None) or []
    for st in subtasks:
        if getattr(st, "key", None):
            neigh.add(st.key)

    # Issue links
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
        logger.warning("Epic Link custom field not found; initial JQL will be limited")
        return []
    jql = f'cf[{epic_link_cf}] = "{epic_key}"'
    return jira.search_issues(jql, fields=fields_csv, maxResults=1000)

def collect_issue_keys_for_epic(epic_key: str, max_depth: int = MAX_DEPTH_DEFAULT) -> List:
    """
    BFS walk from all issues in the epic across links/parent/child up to max_depth.
    Returns fully-fetched issue objects (deduped).
    """
    jira = get_client()
    sp_cf = get_field_id(jira, "Story Points")  # your helper that caches field ids
    epic_link_cf = get_field_id(jira, "Epic Link")

    # fields we need
    base_fields = ["issuetype", "issuelinks", "parent", "subtasks", "status"]
    fields_csv = ",".join(sorted(set(base_fields + ([sp_cf] if sp_cf else []))))

    # seed frontier with items in the Epic
    seeds = _initial_children_for_epic(jira, epic_key, epic_link_cf, fields_csv)
    visited: Set[str] = set([epic_key])  # include the epic key itself (not counted)
    issues_by_key: Dict[str, object] = {}

    frontier = list(seeds)
    for iss in seeds:
        issues_by_key[iss.key] = iss
        visited.add(iss.key)

    depth = 0
    while frontier and depth < max_depth:
        # collect neighbor keys
        neigh_keys: List[str] = []
        for iss in frontier:
            neigh_keys.extend(_expand_neighbors(iss))
        # next wave = those not visited
        next_keys = [k for k in set(neigh_keys) if k not in visited]
        if not next_keys:
            break
        # fetch in batch
        next_issues = _fetch_batch_by_keys(jira, next_keys, fields_csv)
        frontier = []
        for iss in next_issues:
            issues_by_key[iss.key] = iss
            visited.add(iss.key)
            frontier.append(iss)
        depth += 1

    # (Optional) include the Epic itself in collection (doesn’t carry points typically)
    return list(issues_by_key.values())

def compute_point_totals(issues: Iterable, sp_cf: str | None) -> Tuple[float, float, float]:
    bug_pts = 0.0
    story_pts = 0.0
    for iss in issues:
        itype = getattr(getattr(iss.fields, "issuetype", None), "name", "")
        pts = _points(iss.fields, sp_cf)
        if itype in BUG_TYPES:
            bug_pts += pts
        elif itype in STORY_TYPES:
            story_pts += pts
        # else ignore
    total = bug_pts + story_pts
    return round(bug_pts, 2), round(story_pts, 2), round(total, 2)

def upsert_burndown_row(run_dt: date, epic_key: str, bug: float, story: float, total: float) -> None:
    conn = db_utils.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.tbl_compdiv_burndown (run_date, epic_key, bug_points, story_points, total_points)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (run_date, epic_key)
                DO UPDATE SET bug_points=EXCLUDED.bug_points,
                              story_points=EXCLUDED.story_points,
                              total_points=EXCLUDED.total_points;
            """, (run_dt, epic_key, bug, story, total))
        conn.commit()
    finally:
        db_utils.put_conn(conn)

def run_for_all_compdiv_epics(run_dt: date | None = None) -> Dict[str, Tuple[float,float,float]]:
    """Load epic keys from tbl_initiative_issue_keys and compute/store today’s totals for each."""
    run_dt = run_dt or date.today()
    conn = db_utils.get_conn()
    keys: List[str] = []
    try:
        with conn.cursor() as cur:
            cur.execute("""
              SELECT DISTINCT issue_key
              FROM public.tbl_initiative_issue_keys
              WHERE issue_key ~ '^COMPDIV-\\d+$'
            """)
            keys = [r[0] for r in cur.fetchall()]
    finally:
        db_utils.put_conn(conn)

    jira = get_client()
    sp_cf = get_field_id(jira, "Story Points")

    results: Dict[str, Tuple[float,float,float]] = {}
    for epic in keys:
        try:
            issues = collect_issue_keys_for_epic(epic, MAX_DEPTH_DEFAULT)
            bug, story, total = compute_point_totals(issues, sp_cf)
            upsert_burndown_row(run_dt, epic, bug, story, total)
            results[epic] = (bug, story, total)
            logger.info("COMPDIV burndown %s: bug=%s story=%s total=%s", epic, bug, story, total)
        except Exception as e:
            logger.exception("Failed burndown for %s: %s", epic, e)
    return results

# ---------- Prediction + chart ----------

def _linear_zero_day_with_ci(dates: List[date], totals: List[float], conf: float=0.80):
    """Fit y = a + b t ; return t0 date and [lo, hi] (80% CI) when y=0 via delta method.
       Returns (t0_date, lo_date, hi_date) or (None, None, None) if not computable.
    """
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

    a, b = beta[0], beta[1]
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
    db =  a / (b*b)
    var_t0 = (da**2) * cov_beta[0,0] + (db**2) * cov_beta[1,1] + 2*da*db*cov_beta[0,1]
    se_t0 = math.sqrt(max(0.0, var_t0))

    # z for two-sided central 80%
    z = 1.2815515655446004
    lo = t_zero - z * se_t0
    hi = t_zero + z * se_t0

    def clamp_to_dates(x):
        # limit to a reasonable window
        x = max(x, 0.0)
        return t0 + timedelta(days=float(x))

    return (clamp_to_dates(t_zero), clamp_to_dates(lo), clamp_to_dates(hi))

def fetch_burndown_series(epic_key: str) -> Tuple[List[date], List[float], List[float], List[float]]:
    conn = db_utils.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
              SELECT run_date, bug_points, story_points, total_points
              FROM public.tbl_compdiv_burndown
              WHERE epic_key = %s
              ORDER BY run_date ASC
            """, (epic_key,))
            rows = cur.fetchall()
    finally:
        db_utils.put_conn(conn)

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
        fig.add_trace(go.Scatter(x=dates, y=bug,   mode="lines+markers", name="Bug points"))
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
        template="plotly_white"
    )
    # Return self-contained HTML snippet
    import plotly.io as pio
    return pio.to_html(fig, full_html=True, include_plotlyjs="cdn")
