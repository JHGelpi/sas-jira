"""
Debug script to test forecast function with real burndown data.
"""
import sys
import os
from datetime import date, timedelta
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jira_automation.burndown_forecast import constrained_linear_forecast
from jira_automation.jira_burndown import fetch_burndown_series

load_dotenv()

def test_with_real_data(epic_key: str):
    """Test forecast with real data from database."""
    print(f"\n{'='*70}")
    print(f"Testing forecast for {epic_key}")
    print('='*70)

    try:
        dates, bug_pts, story_pts, task_pts, total_pts = fetch_burndown_series(epic_key)

        if not dates:
            print(f"❌ No data found for {epic_key}")
            return

        print(f"\n📊 Data Summary:")
        print(f"   Data points: {len(dates)}")
        print(f"   Date range: {dates[0]} to {dates[-1]}")
        print(f"   Days span: {(dates[-1] - dates[0]).days}")
        print(f"   Total points - First: {total_pts[0]:.1f}, Last: {total_pts[-1]:.1f}")
        print(f"   Change: {total_pts[0] - total_pts[-1]:.1f} points")

        if len(dates) >= 3:
            # Calculate manual slope for comparison
            days_span = (dates[-1] - dates[0]).days
            if days_span > 0:
                manual_slope = (total_pts[-1] - total_pts[0]) / days_span
                print(f"   Manual slope: {manual_slope:.4f} pts/day")

                # Calculate what minimum slope should be
                intercept_approx = total_pts[0]
                min_slope = -intercept_approx / 365
                print(f"   Min required slope: {min_slope:.4f} pts/day (for {intercept_approx:.1f} pts)")
                print(f"   Constraint check: {manual_slope:.4f} <= {min_slope:.4f}? {manual_slope <= min_slope}")

        print(f"\n🔍 Running constrained_linear_forecast...")
        zero_date, ci_lower, ci_upper = constrained_linear_forecast(dates, total_pts)

        if zero_date:
            print(f"\n✅ FORECAST GENERATED:")
            print(f"   Zero date: {zero_date}")
            print(f"   Days from start: {(zero_date - dates[0]).days}")
            print(f"   80% CI: [{ci_lower}, {ci_upper}]")
            if ci_lower and ci_upper:
                print(f"   CI width: {(ci_upper - ci_lower).days} days")
        else:
            print(f"\n❌ NO FORECAST (constraint violated or insufficient data)")
            print(f"   This epic's burndown is too slow (>365 days to completion)")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

def test_sample_data():
    """Test with known sample data."""
    print(f"\n{'='*70}")
    print("Testing with sample data (fast burndown)")
    print('='*70)

    # Fast burndown - should produce forecast
    dates = [date(2025, 1, 1) + timedelta(days=i*10) for i in range(7)]
    totals = [100, 85, 70, 55, 40, 25, 10]

    print(f"Data points: {len(dates)}")
    print(f"Points: {totals}")

    zero_date, ci_lower, ci_upper = constrained_linear_forecast(dates, totals)

    if zero_date:
        print(f"✅ Zero date: {zero_date} ({(zero_date - dates[0]).days} days)")
    else:
        print("❌ No forecast generated")

    # Slow burndown - should NOT produce forecast
    print(f"\n{'='*70}")
    print("Testing with sample data (slow burndown)")
    print('='*70)

    dates2 = [date(2025, 1, 1) + timedelta(days=i*50) for i in range(10)]
    totals2 = [100, 90, 80, 70, 60, 50, 40, 30, 20, 10]

    print(f"Data points: {len(dates2)}")
    print(f"Points: {totals2}")

    zero_date2, ci_lower2, ci_upper2 = constrained_linear_forecast(dates2, totals2)

    if zero_date2:
        print(f"❌ UNEXPECTED: Zero date: {zero_date2}")
    else:
        print("✅ No forecast (as expected - too slow)")

if __name__ == "__main__":
    # Test with sample data first
    test_sample_data()

    # Test with real epics
    test_epics = [
        "COMPDIV-130",
        "COMPDIV-132",
        "COMPDIV-238",
        "COMPDIV-250",
    ]

    for epic in test_epics:
        test_with_real_data(epic)

    print(f"\n{'='*70}")
    print("Debug complete")
    print('='*70)
