#!/usr/bin/env python3
"""
Quick verification script to show which Teams webhook is configured and will be used.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

v2_url = os.getenv('TEAMS_WEBHOOK_URL_V2')
legacy_url = os.getenv('TEAMS_WEBHOOK_URL')

print("=" * 80)
print("TEAMS WEBHOOK CONFIGURATION VERIFICATION")
print("=" * 80)
print()

if v2_url:
    print("✅ TEAMS_WEBHOOK_URL_V2 (Power Automate) is configured")
    print(f"   URL snippet: ...{v2_url[-50:]}")
    is_power_automate = 'powerplatform.com' in v2_url or 'powerautomate' in v2_url
    print(f"   Detected as: {'Power Automate' if is_power_automate else 'Unknown'} webhook")
    print(f"   Will be used: YES (V2 has priority)")
else:
    print("❌ TEAMS_WEBHOOK_URL_V2 is NOT configured")

print()

if legacy_url:
    print(f"{'✅' if not v2_url else 'ℹ️'} TEAMS_WEBHOOK_URL (legacy) is configured")
    print(f"   URL snippet: ...{legacy_url[-50:]}")
    print(f"   Will be used: {'YES (V2 not available)' if not v2_url else 'NO (V2 takes priority)'}")
else:
    print("❌ TEAMS_WEBHOOK_URL (legacy) is NOT configured")

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)

if v2_url:
    print("✅ System will use Power Automate V2 webhook")
    print("   Migration to new webhook format: COMPLETE")
elif legacy_url:
    print("⚠️  System will use legacy Office 365 Connector webhook")
    print("   Recommendation: Configure TEAMS_WEBHOOK_URL_V2 for future compatibility")
else:
    print("❌ NO webhook URLs configured - Teams notifications disabled")

print()
