import os
import requests
import logging

# Use the centralized logging system
logger = logging.getLogger(__name__)

def send_teams_notification(title: str, body_elements: list, mentions: list = None):
    """
    Sends a formatted Adaptive Card notification to a Microsoft Teams channel,
    with support for @mentions.

    Args:
        title (str): The main title of the notification card.
        body_elements (list): A list of Adaptive Card body elements (e.g., TextBlocks, FactSets).
        mentions (list, optional): A list of dicts for users to mention, 
                                   e.g., [{'name': 'User Name', 'email': 'user@example.com'}].
    """
    webhook_url = os.getenv('TEAMS_WEBHOOK_URL')
    if not webhook_url:
        logger.warning("TEAMS_WEBHOOK_URL not set. Skipping notification.")
        return

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

    # Structure the message using Teams' "Adaptive Card" format for rich content
    payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "type": "AdaptiveCard",
                    "version": "1.4", # Using a modern version for better formatting
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
                        # Unpack the rest of the body elements here
                        *body_elements
                    ]
                }
            }
        ]
    }

    try:
        logger.info(f"Sending notification to Teams for: {title}")
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info("✅ Successfully sent Teams notification.")
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Failed to send Teams notification: {e}")

