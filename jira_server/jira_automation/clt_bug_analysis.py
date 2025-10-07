# jira_automation/clt_bug_analysis.py

from __future__ import annotations

import logging
import os
from typing import List

from dotenv import load_dotenv
from jira import JIRA

# We delegate rendering to the existing customer_analysis module so
# the columns/colors/layout match exactly.
try:
    # If running as part of the jira_automation package
    from . import customer_analysis as base_report
except Exception:  # pragma: no cover
    # Fallback if run as a loose script
    import customer_analysis as base_report  # type: ignore

logger = logging.getLogger(__name__)
JIRA_TIMEOUT_SECONDS = int(os.getenv("JIRA_TIMEOUT") or 30)


# ---------------------------
# Jira helpers
# ---------------------------
def _get_jira_client() -> JIRA:
    load_dotenv()
    url = os.getenv("JIRA_URL")
    token = os.getenv("JIRA_TOKEN")
    if not url or not token:
        raise RuntimeError("Jira credentials missing. Set JIRA_URL and JIRA_TOKEN in environment or .env")
    jira = JIRA(server=url, token_auth=token, options={"timeout": JIRA_TIMEOUT_SECONDS})
    try:
        info = jira.server_info()
        logger.info("Connected to Jira: %s", info.get("version"))
    except Exception:  # best-effort log
        logger.info("Connected to Jira")
    return jira


def _search_all_issues(jira: JIRA, jql: str, fields: str = "*all", batch_size: int = 1000) -> List[object]:
    """Return all issues for the given JQL, handling pagination."""
    issues: List[object] = []
    start_at = 0
    while True:
        chunk = jira.search_issues(jql, startAt=start_at, maxResults=batch_size, fields=fields)
        if not chunk:
            break
        issues.extend(chunk)
        if len(chunk) < batch_size:
            break
        start_at += len(chunk)
    return issues


# ---------------------------
# Dispatch into customer_analysis
# ---------------------------
def _handoff_to_customer_analysis(issues: List[object]) -> None:
    """
    Call into customer_analysis using the most likely entry points.
    This preserves existing columns/colors/formatting.
    """
    # 1) Preferred: a function that renders directly from issues
    for fn_name in ("render_from_issues", "generate_report_from_issues", "make_report_from_issues"):
        fn = getattr(base_report, fn_name, None)
        if callable(fn):
            fn(issues)  # type: ignore[misc]
            return

    # 2) Build a DataFrame via a helper then render it
    build_df = getattr(base_report, "build_dataframe", None)
    render_df = getattr(base_report, "render_report", None) or getattr(base_report, "render_dataframe", None)
    if callable(build_df) and callable(render_df):
        df = build_df(issues)  # type: ignore[misc]
        render_df(df)          # type: ignore[misc]
        return

    # 3) Last resort: a single-shot function that takes JIRA + issues
    for fn_name in ("generate_report", "make_report"):
        fn = getattr(base_report, fn_name, None)
        if callable(fn):
            try:
                fn(issues)  # type: ignore[misc]
                return
            except TypeError:
                pass

    raise RuntimeError(
        "Could not find a suitable entry point in customer_analysis to render the report. "
        "Please expose one of: render_from_issues(issues), build_dataframe(issues)+render_report(df), "
        "or generate_report(issues)."
    )


# ---------------------------
# Main
# ---------------------------
def main() -> None:
    load_dotenv()
    jql = os.getenv("JQL_CLT_BUGS", "").strip()
    if not jql:
        raise RuntimeError(
            "JQL_CLT_BUGS is not set. Add it to your environment or .env, e.g.\n"
            'JQL_CLT_BUGS=project = CLT AND issuetype = Bug AND labels = "customer-impact"'
        )

    logger.info("Running CLT bug analysis with JQL from JQL_CLT_BUGS:\n%s", jql)
    jira = _get_jira_client()
    issues = _search_all_issues(jira, jql, fields="*all")
    logger.info("Fetched %d issues for CLT bug analysis.", len(issues))

    _handoff_to_customer_analysis(issues)
    logger.info("CLT bug analysis completed successfully.")


if __name__ == "__main__":
    # Minimal logging if not already configured by the app
