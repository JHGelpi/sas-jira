#!/usr/bin/env python3
"""
Test script for the new Teams webhook V2 integration.

This script sends a test notification using the updated notification_utils
to verify the Power Automate webhook integration works correctly.
"""

import os
import sys
from dotenv import load_dotenv
from logging_config import setup_logging
from logging_utils import get_logger

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jira_automation import notification_utils

logger = get_logger(__name__)

def main():
    """Send a test notification to verify webhook V2 functionality."""
    setup_logging()

    # Load environment variables
    project_root = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(dotenv_path=os.path.join(project_root, '.env'))

    logger.info("Starting Teams webhook V2 test")

    # Check which webhook URLs are configured
    v2_url = os.getenv('TEAMS_WEBHOOK_URL_V2')
    legacy_url = os.getenv('TEAMS_WEBHOOK_URL')

    if v2_url:
        logger.info(f"✓ TEAMS_WEBHOOK_URL_V2 is configured (Power Automate)")
    else:
        logger.warning("✗ TEAMS_WEBHOOK_URL_V2 is not set")

    if legacy_url:
        logger.info(f"✓ TEAMS_WEBHOOK_URL (legacy) is configured")
    else:
        logger.warning("✗ TEAMS_WEBHOOK_URL (legacy) is not set")

    if not v2_url and not legacy_url:
        logger.error("No webhook URLs configured. Cannot send test notification.")
        return

    # Create a test notification
    title = "🧪 Teams Webhook V2 Test"

    body_elements = [
        {
            "type": "TextBlock",
            "text": "This is a test notification to verify the new Power Automate webhook integration is working correctly.",
            "wrap": True
        },
        {
            "type": "FactSet",
            "facts": [
                {"title": "Test Time:", "value": "Now"},
                {"title": "Webhook Version:", "value": "V2 (Power Automate)" if v2_url else "Legacy"},
                {"title": "Status:", "value": "✅ Integration Active"}
            ],
            "separator": True
        },
        {
            "type": "TextBlock",
            "text": "If you're seeing this message, the webhook migration was successful!",
            "wrap": True,
            "weight": "Bolder",
            "color": "Good"
        }
    ]

    # Send test notification (without mentions for simplicity)
    logger.info("Sending test notification...")
    notification_utils.send_teams_notification(title, body_elements)

    logger.info("Test completed. Check your Teams channel for the notification.")

if __name__ == "__main__":
    main()
