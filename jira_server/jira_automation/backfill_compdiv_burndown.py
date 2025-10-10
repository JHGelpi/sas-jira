from __future__ import annotations
# -----------------------------
# File: scripts/backfill_compdiv_burndown.py
# Purpose: One-time backfill of current ("as-is") totals into past business days
#          for COMPDIV epics flagged with filter_flag = 'BURNDWN'.
# Usage:
#   # Optional overrides via env vars:
#   #   COMPDIV_BACKFILL_START=2025-07-01
#   #   COMPDIV_BACKFILL_END=2025-09-29
#   #   COMPDIV_BACKFILL_FLAG=BURNDWN
#   #   COMPDIV_SKIP_HTML=1   # recommended to speed up backfill
#   python -m scripts.backfill_compdiv_burndown

# --- BEGIN backfill_compdiv_burndown.py ---

#import logging
import os
from datetime import date, timedelta, datetime

from dotenv import load_dotenv

from jira_automation.compdiv_burndown import run_for_all_compdiv_epics

from logging_utils import get_logger

logger = get_logger(__name__)

def business_days(start: date, end: date):
    d = start
    while d <= end:
        if d.weekday() < 5:  # Mon-Fri
            yield d
        d += timedelta(days=1)


def _parse_date_env(name: str, default: date) -> date:
    s = os.getenv(name, "").strip()
    if not s:
        return default
    # Accept YYYY-MM-DD or DD-Mon-YYYY
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%B-%Y"):
        try:
            s_try = s
            if fmt in ("%d-%b-%Y", "%d-%B-%Y"):
                parts = s.split("-")
                if len(parts) == 3:
                    parts[1] = parts[1].capitalize()
                    s_try = "-".join(parts)
            return datetime.strptime(s_try, fmt).date()
        except Exception:
            continue
    raise ValueError(f"Could not parse {name}={s!r}. Use YYYY-MM-DD or DD-Mon-YYYY (e.g., 2025-07-01 or 01-Jul-2025).")


def main():
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    # Defaults per request
    start_default = date(2025, 7, 1)
    end_default = date(2025, 9, 29)

    start = _parse_date_env("COMPDIV_BACKFILL_START", start_default)
    end = _parse_date_env("COMPDIV_BACKFILL_END", end_default)
    if start > end:
        start, end = end, start

    # Ensure we only process BURNDWN epics
    filter_flag = os.getenv("COMPDIV_BACKFILL_FLAG", "BURNDWN").strip() or "BURNDWN"

    # Optional: skip chart writes during backfill to save time/disk
    os.environ.setdefault("COMPDIV_SKIP_HTML", "1")

    logging.info("Backfill starting for business days %s -> %s, filter_flag=%s", start, end, filter_flag)
    total_runs = 0
    for d in business_days(start, end):
        total_runs += 1
        logging.info("Backfill run for %s...", d)
        run_for_all_compdiv_epics(run_dt=d, filter_flag=filter_flag)

    logging.info("Backfill complete. Days processed: %d", total_runs)


if __name__ == "__main__":
    main()
# --- END scripts/backfill_compdiv_burndown.py ---