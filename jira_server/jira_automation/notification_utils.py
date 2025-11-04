import os
import requests
#import logging

# Use the centralized logging system
from logging_utils import get_logger

logger = get_logger(__name__)

def send_teams_notification(title: str, body_elements: list, mentions: list = None):
    """
    Sends a formatted Adaptive Card notification to a Microsoft Teams channel,
    with support for @mentions.

    Supports both legacy Office 365 Connector webhooks and new Power Automate HTTP trigger webhooks.

    Args:
        title (str): The main title of the notification card.
        body_elements (list): A list of Adaptive Card body elements (e.g., TextBlocks, FactSets).
        mentions (list, optional): A list of dicts for users to mention,
                                   e.g., [{'name': 'User Name', 'email': 'user@example.com'}].
    """
    # Try V2 webhook first, fallback to legacy if not set
    webhook_url = os.getenv('TEAMS_WEBHOOK_URL_V2') or os.getenv('TEAMS_WEBHOOK_URL')
    if not webhook_url:
        logger.warning("Neither TEAMS_WEBHOOK_URL_V2 nor TEAMS_WEBHOOK_URL is set. Skipping notification.")
        return

    # Determine if using the new Power Automate webhook format
    is_power_automate_webhook = 'powerplatform.com' in webhook_url or 'powerautomate' in webhook_url

    logger.debug(f"Using {'Power Automate' if is_power_automate_webhook else 'legacy Office 365 Connector'} webhook format")

    msteams_mention_entities = []
    if mentions:
        for mention in mentions:
            if mention.get('name') and mention.get('email'):
                msteams_mention_entities.append({
                    "type": "mention",
                    "text": f"<at>{mention['name']}</at>",
                    "mentioned": {
                        "id": mention['email'],
                        "name": mention['name']
                    }
                })

    # Prepend the mention text to the top of the card for visibility
    if msteams_mention_entities:
        mention_text_block = {
            "type": "TextBlock",
            "text": " ".join([m['text'] for m in msteams_mention_entities]),
            "wrap": True
        }
        # Insert the mentions as the first element after the title
        body_elements.insert(0, mention_text_block)

    # Build the adaptive card content
    adaptive_card_content = {
        "type": "AdaptiveCard",
        "version": "1.4",
        "msteams": {
            "width": "Full",
            "entities": msteams_mention_entities
        },
        "body": [
            {
                "type": "TextBlock",
                "text": title,
                "size": "Large",
                "weight": "Bolder"
            },
            *body_elements
        ]
    }

    # Format payload based on webhook type
    if is_power_automate_webhook:
        # New Power Automate format - send Adaptive Card content directly
        # Power Automate flows expect the card content to be posted directly via Teams connector
        # Mentions in Power Automate Teams connector work differently - need to use text mentions only
        # Remove msteams.entities for Power Automate as the connector handles this differently
        if 'msteams' in adaptive_card_content:
            # Keep width but remove entities - Power Automate Teams connector doesn't support mention entities
            adaptive_card_content['msteams'] = {"width": "Full"}

        payload = adaptive_card_content
    else:
        # Legacy Office 365 Connector format
        payload = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": adaptive_card_content
                }
            ]
        }

    try:
        logger.info(f"Sending notification to Teams for: {title}")
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        logger.success("Successfully sent Teams notification")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send Teams notification: {e}")
        if hasattr(e.response, 'text'):
            logger.error(f"Response details: {e.response.text}")

