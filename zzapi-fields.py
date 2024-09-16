#API Fields
import json
from jira import JIRA
from datetime import datetime

def main():
    # Configuration
    options = {'server': 'https://rndjira.sas.com/'}
    file_path = '/Users/wegelpi/encrypt/secrets/jira-token.txt'

    # Generate a timestamp for the filename
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    output_json_path = f'/Users/wegelpi/Downloads/jira_fields-{timestamp}.json'

    # Read API token from file
    try:
        with open(file_path, 'r') as file:
            jira_api_token = file.read().strip()
    except IOError as e:
        print(f"Error reading from file: {e}")
        return

    # Connect to JIRA and fetch fields
    try:
        jira = JIRA(options=options)
        jira._session.headers.update({'Authorization': f'Bearer {jira_api_token}'})
        fields = jira.fields()

        # Write fields information to a JSON file
        with open(output_json_path, 'w') as json_file:
            json.dump(fields, json_file, indent=4)
        print(f"Fields information exported successfully to {output_json_path}")

    except Exception as e:
        print(f"Failed to authenticate or retrieve data: {e}")
        if hasattr(e, 'response'):
            print("Status code:", e.response.status_code)
            print("Error response:", e.response.text)

if __name__ == "__main__":
    main()
