"""
Shared forecasting logic for COMPDIV and IRIS burndown charts.

Implements constrained linear regression with 365-day maximum completion horizon.
When the natural burndown slope is too shallow (would predict completion > 365 days),
returns no forecast instead of showing an unrealistic prediction.

This module eliminates code duplication between compdiv_burndown.py and iris_burndown.py.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import List, Tuple, Optional

import numpy as np


# Constants
MAX_FORECAST_DAYS = 365
MIN_DATA_POINTS = 3
NEARLY_ZERO_SLOPE = 1e-6
Z_SCORE_80PCT = 1.2815515655446004  # z-score for 80% confidence interval


def constrained_linear_forecast(
    dates: List[date],
    totals: List[float],
    conf: float = 0.80,
    max_lookahead_days: int = 0
) -> Tuple[Optional[date], Optional[date], Optional[date]]:
    """
    Fit constrained linear regression with 365-day maximum completion horizon.

    Uses Ordinary Least Squares (OLS) to fit y = a + b*t where:
        y = story points remaining
        t = days since first observation
        a = y-intercept (initial points estimate)
        b = slope (daily burn rate)

    **Constraint**: If the slope violates b <= -a/365, returns (None, None, None).
    This ensures forecasts predict completion within 365 days maximum.

    Parameters
    ----------
    dates : List[date]
        Observation dates (must be sorted chronologically)
    totals : List[float]
        Points remaining at each date
    conf : float, default 0.80
        Confidence level for CI (0.80 = 80%)
    max_lookahead_days : int, default 0
        Optional horizon limit (0 = disabled). If > 0, forecasts beyond
        this many days from first date return None.

    Returns
    -------
    Tuple[Optional[date], Optional[date], Optional[date]]
        (zero_date, ci_lower, ci_upper)
        - All dates are None if no valid forecast can be made

    Algorithm
    ---------
    1. Validate inputs (≥ 3 data points required)
    2. Normalize time to days from earliest date
    3. Perform OLS regression: y = a + b*t
    4. **Check constraint**: If b > -a/365, return (None, None, None)
    5. Calculate zero-crossing: t_zero = -a/b
    6. Compute 80% confidence interval using Delta Method
    7. Apply optional lookahead horizon limit (from env vars)
    8. Return (zero_date, ci_lower, ci_upper)

    Edge Cases
    ----------
    Returns (None, None, None) if:
        - len(dates) < 3 (insufficient data)
        - a <= 0 (non-positive intercept)
        - b >= 0 (not burning down)
        - abs(b) < 1e-6 (essentially flat)
        - b > -a/365 (too shallow - violates 365-day constraint) ← NEW
        - OLS singular matrix
        - Forecast exceeds max_lookahead_days (if configured)

    Examples
    --------
    >>> # Aggressive burndown: 100 points over 60 days
    >>> dates = [date(2025, 1, 1) + timedelta(days=i*10) for i in range(7)]
    >>> totals = [100, 85, 70, 55, 40, 25, 10]
    >>> zero, lo, hi = constrained_linear_forecast(dates, totals)
    >>> zero  # Should produce forecast (burns fast enough)
    date(2025, 3, ...)

    >>> # Slow burndown: 100 points over 500 days
    >>> dates = [date(2025, 1, 1) + timedelta(days=i*50) for i in range(10)]
    >>> totals = [100, 90, 80, 70, 60, 50, 40, 30, 20, 10]
    >>> zero, lo, hi = constrained_linear_forecast(dates, totals)
    >>> zero  # Should return None (too shallow)
    None
    """
    # 1. Validate inputs
    if len(dates) < MIN_DATA_POINTS:
        return (None, None, None)

    # 2. Normalize time to days from t0
    t0 = min(dates)
    t = np.array([(d - t0).days for d in dates], dtype=float)
    y = np.array(totals, dtype=float)

    # 3. OLS regression: y = a + b*t
    X = np.column_stack([np.ones_like(t), t])
    XtX = X.T @ X

    try:
        beta = np.linalg.inv(XtX) @ (X.T @ y)
    except np.linalg.LinAlgError:
        return (None, None, None)

    a, b = float(beta[0]), float(beta[1])

    # 4. Edge case: non-positive intercept
    if a <= 0:
        return (None, None, None)

    # 5. Edge case: not burning down or essentially flat
    if b >= 0 or abs(b) < NEARLY_ZERO_SLOPE:
        return (None, None, None)

    # 6. **NEW**: Check 365-day constraint
    # The slope must satisfy: b <= -a/365
    # This ensures completion within 365 days maximum
    b_min = -a / MAX_FORECAST_DAYS  # Most negative acceptable slope (e.g., -0.274 for a=100)

    if b > b_min:  # b is too shallow (e.g., -0.2 > -0.274)
        # Slope violates constraint - would predict completion > 365 days
        return (None, None, None)

    # 7. Calculate zero-crossing (in days from t0)
    t_zero = -a / b

    # 8. Confidence interval calculation using Delta Method
    # Compute residual variance & covariance matrix
    yhat = X @ beta
    resid = y - yhat
    dof = max(1, len(y) - 2)
    sigma2 = float((resid @ resid) / dof)
    cov_beta = sigma2 * np.linalg.inv(XtX)

    # Delta method for Var(t_zero) where t_zero = -a/b
    # Partial derivatives:
    #   ∂(t_zero)/∂a = -1/b
    #   ∂(t_zero)/∂b = a/b²
    da = -1.0 / b
    db = a / (b * b)
    var_t0 = (da * da) * cov_beta[0, 0] + (db * db) * cov_beta[1, 1] + 2 * da * db * cov_beta[0, 1]
    se_t0 = math.sqrt(max(0.0, var_t0))

    # 9. Compute CI bounds
    z = _get_z_score(conf)
    lo_days = t_zero - z * se_t0
    hi_days = t_zero + z * se_t0

    # 10. Convert to dates with safety checks and horizon enforcement
    def to_date_or_none(days_from_t0: float) -> Optional[date]:
        """Convert days to date with safety checks."""
        # Negative or non-finite -> no forecast
        if not math.isfinite(days_from_t0) or days_from_t0 < 0:
            return None

        # Enforce horizon if configured (> 0 means enabled)
        if max_lookahead_days > 0 and days_from_t0 > max_lookahead_days:
            return None

        try:
            return t0 + timedelta(days=days_from_t0)
        except OverflowError:
            return None

    zero_date = to_date_or_none(t_zero)
    ci_lower = to_date_or_none(lo_days)
    ci_upper = to_date_or_none(hi_days)

    return (zero_date, ci_lower, ci_upper)


def _get_z_score(conf: float) -> float:
    """
    Get z-score for confidence level.

    Hardcodes common values to avoid scipy dependency.
    Falls back to 80% if confidence level not recognized.

    Parameters
    ----------
    conf : float
        Confidence level (e.g., 0.80 for 80%)

    Returns
    -------
    float
        Corresponding z-score from standard normal distribution
    """
    if abs(conf - 0.80) < 0.001:
        return 1.2815515655446004  # 80% CI
    elif abs(conf - 0.90) < 0.001:
        return 1.6448536269514722  # 90% CI
    elif abs(conf - 0.95) < 0.001:
        return 1.9599639845400545  # 95% CI
    else:
        # Default to 80% if unrecognized
        return 1.2815515655446004
