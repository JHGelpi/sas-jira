"""
Test cases for constrained burndown forecast methodology.

This test suite validates the 365-day maximum completion constraint
implemented in jira_automation/burndown_forecast.py.

Run with:
    cd /Users/wegelpi/github_repos/sas-jira/jira_server
    source venv/bin/activate
    python test_burndown_forecast.py
"""

from datetime import date, timedelta
from jira_automation.burndown_forecast import constrained_linear_forecast


def test_unconstrained_case():
    """Test normal case where natural slope is steep enough."""
    print("\n--- Test 1: Unconstrained Case (Fast Burndown) ---")

    # Simulate aggressive burndown: 100 points over ~60 days (~1.67 pts/day)
    # This burns down much faster than minimum required (100/365 = 0.274 pts/day)
    dates = [date(2025, 1, 1) + timedelta(days=i*10) for i in range(7)]
    totals = [100, 85, 70, 55, 40, 25, 10]

    zero_date, lo, hi = constrained_linear_forecast(dates, totals)

    assert zero_date is not None, "Should produce forecast for fast burndown"
    assert lo is not None, "Should have CI lower bound"
    assert hi is not None, "Should have CI upper bound"
    assert zero_date < date(2025, 5, 1), "Should complete within ~60-80 days"
    assert lo <= hi, "CI lower bound should be before or equal to upper bound"

    print(f"  ✓ Zero date: {zero_date}")
    print(f"  ✓ 80% CI: [{lo}, {hi}]")
    print(f"  ✓ Days from start: {(zero_date - dates[0]).days}")
    print("  ✓ PASS: Forecast produced (slope steep enough)")


def test_constrained_case():
    """Test case where natural slope is too shallow (violates constraint)."""
    print("\n--- Test 2: Constrained Case (Slow Burndown) ---")

    # Simulate slow burndown: 100 points over ~450 days (~0.22 pts/day)
    # This is slower than minimum required (100/365 = 0.274 pts/day)
    dates = [date(2025, 1, 1) + timedelta(days=i*50) for i in range(10)]
    totals = [100, 90, 80, 70, 60, 50, 40, 30, 20, 10]

    zero_date, lo, hi = constrained_linear_forecast(dates, totals)

    assert zero_date is None, "Should return None for slow burndown"
    assert lo is None, "CI should be None when no forecast"
    assert hi is None, "CI should be None when no forecast"

    print("  ✓ Zero date: None (as expected)")
    print("  ✓ Constraint enforced: Slope too shallow (would exceed 365 days)")
    print("  ✓ PASS: No forecast shown for unrealistic timeline")


def test_boundary_case_exactly_365_days():
    """Test boundary case where burndown completes in exactly 365 days."""
    print("\n--- Test 3: Boundary Case (Exactly 365 Days) ---")

    # Create data that should yield slope = -100/365 ≈ -0.274
    # With 12 monthly data points over 330 days
    dates = [date(2025, 1, 1) + timedelta(days=i*30) for i in range(12)]
    # Linear decrease: 100 down to ~9.6 over 330 days
    totals = [100 - (i * 30 * 100 / 365) for i in range(12)]

    zero_date, lo, hi = constrained_linear_forecast(dates, totals)

    # Should produce forecast since slope is approximately at the minimum threshold
    assert zero_date is not None, "Should produce forecast at boundary"
    assert lo is not None, "Should have CI lower bound"
    assert hi is not None, "Should have CI upper bound"

    days_to_zero = (zero_date - dates[0]).days
    print(f"  ✓ Zero date: {zero_date}")
    print(f"  ✓ Days from start: {days_to_zero}")
    print(f"  ✓ Expected: ~365 days (actual may vary due to data noise)")
    print("  ✓ PASS: Forecast produced at boundary condition")


def test_edge_case_positive_slope():
    """Test case where points are increasing (negative burndown)."""
    print("\n--- Test 4: Edge Case (Positive Slope) ---")

    dates = [date(2025, 1, 1) + timedelta(days=i*10) for i in range(7)]
    totals = [10, 20, 30, 40, 50, 60, 70]  # Increasing!

    zero_date, lo, hi = constrained_linear_forecast(dates, totals)

    assert zero_date is None, "Should return None for increasing points"
    assert lo is None, "CI should be None"
    assert hi is None, "CI should be None"

    print("  ✓ Zero date: None (as expected)")
    print("  ✓ PASS: No forecast for positive slope (not burning down)")


def test_edge_case_insufficient_data():
    """Test case with < 3 data points."""
    print("\n--- Test 5: Edge Case (Insufficient Data) ---")

    dates = [date(2025, 1, 1), date(2025, 1, 10)]
    totals = [100, 90]

    zero_date, lo, hi = constrained_linear_forecast(dates, totals)

    assert zero_date is None, "Should return None with < 3 data points"
    assert lo is None, "CI should be None"
    assert hi is None, "CI should be None"

    print("  ✓ Zero date: None (as expected)")
    print("  ✓ PASS: No forecast with insufficient data")


def test_edge_case_near_zero_remaining():
    """Test case where remaining work is very small but positive."""
    print("\n--- Test 6: Edge Case (Near-Zero Remaining Work) ---")

    # Epic with small remaining work burning down quickly
    dates = [date(2025, 1, 1) + timedelta(days=i*5) for i in range(5)]
    totals = [5.0, 4.0, 3.0, 2.0, 1.0]

    zero_date, lo, hi = constrained_linear_forecast(dates, totals)

    # Should produce forecast since:
    # 1. Intercept (a) ≈ 5 > 0 (positive)
    # 2. Slope (b) ≈ -1/5 = -0.2 per day
    # 3. Minimum slope: -5/365 ≈ -0.014
    # 4. Since -0.2 < -0.014 (steeper), constraint is satisfied
    assert zero_date is not None, "Should produce forecast for small but positive work"
    print(f"  ✓ Zero date: {zero_date}")
    print(f"  ✓ Days from start: {(zero_date - dates[0]).days}")
    print("  ✓ PASS: Forecast produced for small remaining work")


def test_edge_case_flat_slope():
    """Test case where slope is essentially flat (nearly zero)."""
    print("\n--- Test 7: Edge Case (Flat/Zero Slope) ---")

    dates = [date(2025, 1, 1) + timedelta(days=i*10) for i in range(7)]
    totals = [50.0, 50.1, 49.9, 50.0, 50.1, 49.9, 50.0]  # Oscillating around 50

    zero_date, lo, hi = constrained_linear_forecast(dates, totals)

    assert zero_date is None, "Should return None for flat slope"
    assert lo is None, "CI should be None"
    assert hi is None, "CI should be None"

    print("  ✓ Zero date: None (as expected)")
    print("  ✓ PASS: No forecast for essentially flat slope")


def test_max_lookahead_enforcement():
    """Test that max_lookahead_days parameter is respected."""
    print("\n--- Test 8: Max Lookahead Enforcement ---")

    # Moderate burndown: 100 points over ~180 days
    dates = [date(2025, 1, 1) + timedelta(days=i*20) for i in range(10)]
    totals = [100, 90, 80, 70, 60, 50, 40, 30, 20, 10]

    # First, get forecast without lookahead limit
    zero_no_limit, _, _ = constrained_linear_forecast(dates, totals, max_lookahead_days=0)
    assert zero_no_limit is not None, "Should produce forecast without limit"

    # Now enforce a 60-day lookahead limit (should block forecast)
    zero_with_limit, _, _ = constrained_linear_forecast(dates, totals, max_lookahead_days=60)
    assert zero_with_limit is None, "Should return None when exceeding lookahead limit"

    # With generous 365-day limit (should allow forecast)
    zero_generous, _, _ = constrained_linear_forecast(dates, totals, max_lookahead_days=365)
    assert zero_generous is not None, "Should produce forecast within generous limit"

    print(f"  ✓ No limit: {zero_no_limit}")
    print(f"  ✓ 60-day limit: {zero_with_limit} (None as expected)")
    print(f"  ✓ 365-day limit: {zero_generous}")
    print("  ✓ PASS: Lookahead limit enforced correctly")


def run_all_tests():
    """Run all test cases."""
    print("=" * 70)
    print("BURNDOWN FORECAST CONSTRAINT VALIDATION TEST SUITE")
    print("=" * 70)

    tests = [
        test_unconstrained_case,
        test_constrained_case,
        test_boundary_case_exactly_365_days,
        test_edge_case_positive_slope,
        test_edge_case_insufficient_data,
        test_edge_case_near_zero_remaining,
        test_edge_case_flat_slope,
        test_max_lookahead_enforcement,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"\n  ✗ FAIL: {e}")
            failed += 1
        except Exception as e:
            print(f"\n  ✗ ERROR: {e}")
            failed += 1

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    if failed == 0:
        print("\n✅ ALL TESTS PASSED!\n")
        return True
    else:
        print(f"\n❌ {failed} TEST(S) FAILED\n")
        return False


if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
