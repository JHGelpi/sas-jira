# jira_automation/clt_bug_analysis.py
"""
CLT project bug analysis.

This module runs a JQL query for CLT bugs and delegates to the customer_analysis
module for rendering, ensuring consistent formatting and output.
"""

from __future__ import annotations

import os
from typing import List
from dotenv import load_dotenv
from jira import JIRA
from logging_utils import get_logger, log_section_header

# Delegate rendering to the existing customer_analysis module
try:
    from . import customer_analysis as base_report
except Exception:
    import customer_analysis as base_report  # type: ignore

logger = get_logger(__name__)
JIRA_TIMEOUT_SECONDS = int(os.getenv("JIRA_TIMEOUT") or 30)


def _get_jira_client() -> JIRA:
    """Returns an authenticated Jira client."""
    load_dotenv()
    url = os.getenv("JIRA_URL")
    token = os.getenv("JIRA_TOKEN")
    
    if not url or token:
        raise RuntimeError("Jira credentials missing. Set JIRA_URL and JIRA_TOKEN in environment or .env")
    
    logger.connecting(f"Connecting to Jira server at {url}")
    jira = JIRA(server=url, token_auth=token, options={"timeout": JIRA_TIMEOUT_SECONDS})
    
    try:
        info = jira.server_info()
        logger.success(f"Connected to Jira: {info.get('version')}")
    except Exception:
        logger.success("Connected to Jira")
    
    return jira


def _search_all_issues(jira: JIRA, jql: str, fields: str = "*all", batch_size: int = 1000) -> List[object]:
    """Return all issues for the given JQL, handling pagination."""
    issues: List[object] = []
    start_at = 0
    
    logger.searching("Fetching all issues matching JQL query")
    
    while True:
        chunk = jira.search_issues(jql, startAt=start_at, maxResults=batch_size, fields=fields)
        if not chunk:
            break
        issues.extend(chunk)
        logger.debug(f"Fetched {len(chunk)} issues (total: {len(issues)})")
        if len(chunk) < batch_size:
            break
        start_at += len(chunk)
    
    logger.info(f"Fetched {len(issues)} total issues")
    return issues


def _handoff_to_customer_analysis(issues: List[object]) -> None:
    """
    Call into customer_analysis using the most likely entry points.
    This preserves existing columns/colors/formatting.
    """
    # 1) Preferred: a function that renders directly from issues
    for fn_name in ("render_from_issues", "generate_report_from_issues", "make_report_from_issues"):
        fn = getattr(base_report, fn_name, None)
        if callable(fn):
            logger.processing(f"Delegating to {fn_name}() in customer_analysis")
            fn(issues)  # type: ignore[misc]
            return

    # 2) Build a DataFrame via a helper then render it
    build_df = getattr(base_report, "build_dataframe", None)
    render_df = getattr(base_report, "render_report", None) or getattr(base_report, "render_dataframe", None)
    if callable(build_df) and callable(render_df):
        logger.processing("Delegating via build_dataframe() + render_report()")
        df = build_df(issues)  # type: ignore[misc]
        render_df(df)          # type: ignore[misc]
        return

    # 3) Last resort: a single-shot function that takes JIRA + issues
    for fn_name in ("generate_report", "make_report"):
        fn = getattr(base_report, fn_name, None)
        if callable(fn):
            try:
                logger.processing(f"Delegating to {fn_name}()")
                fn(issues)  # type: ignore[misc]
                return
            except TypeError:
                pass

    raise RuntimeError(
        "Could not find a suitable entry point in customer_analysis to render the report. "
        "Please expose one of: render_from_issues(issues), build_dataframe(issues)+render_report(df), "
        "or generate_report(issues)."
    )


def main() -> None:
    """Main entry point for CLT bug analysis."""
    log_section_header(logger, "CLT BUG ANALYSIS")
    
    load_dotenv()
    jql = os.getenv("JQL_CLT_BUGS", "").strip()
    
    if not jql:
        logger.error(
            "JQL_CLT_BUGS is not set. Add it to your environment or .env, e.g.\n"
            'JQL_CLT_BUGS=project = CLT AND issuetype = Bug AND labels = "customer-impact"'
        )
        return

    logger.info(f"Running CLT bug analysis with JQL from JQL_CLT_BUGS")
    logger.debug(f"Query: {jql}")
    
    jira = _get_jira_client()
    issues = _search_all_issues(jira, jql, fields="*all")
    
    if not issues:
        logger.complete("No CLT bugs found matching the query")
        return
    
    logger.info(f"Processing {len(issues)} CLT bugs")
    _handoff_to_customer_analysis(issues)
    
    logger.complete("CLT bug analysis completed successfully")


if __name__ == "__main__":
    from logging_config import setup_logging
    setup_logging()
    main()