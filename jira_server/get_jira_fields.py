import os
import json
from jira import JIRA
from dotenv import load_dotenv
import logging

# Configure basic logging for this script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    """
    Connects to Jira and prints a list of all available fields.
    """
    # Load environment variables from the .env file in the current directory
    load_dotenv()

    try:
        logging.info(f"Connecting to Jira server at {os.getenv('JIRA_URL')}...")
        jira_client = JIRA(
            server=os.getenv('JIRA_URL'),
            token_auth=os.getenv('JIRA_TOKEN')
        )
        logging.info("Successfully connected to Jira!")
    except Exception as e:
        logging.error(f"Failed to connect to Jira: {e}")
        return

    try:
        logging.info("Fetching all available fields...")
        all_fields = jira_client.fields()
        
        print("\n--- Available Jira Fields ---")
        # Sort the fields alphabetically by name for readability
        for field in sorted(all_fields, key=lambda x: x['name']):
            field_id = field['id']
            field_name = field['name']
            # Add a marker for custom fields
            is_custom = field.get('custom', False)
            custom_marker = "[Custom]" if is_custom else "[System]"
            
            print(f"{field_name:<40} {custom_marker:<10} ID: {field_id}")
            
        print("\n--- End of List ---")

    except Exception as e:
        logging.error(f"An error occurred while fetching fields: {e}")


if __name__ == "__main__":
    main()