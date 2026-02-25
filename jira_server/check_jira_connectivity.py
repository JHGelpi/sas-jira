#!/usr/bin/env python3
"""
Jira Connectivity Check

Verifies that Jira is reachable before running automation scripts.
This prevents cryptic errors when VPN connection is down.

Exit codes:
  0 - Jira is reachable
  1 - Jira is unreachable (VPN likely down)
  2 - Configuration error (missing credentials)
"""

import os
import sys
from jira import JIRA

def check_jira_connectivity():
    """
    Test Jira connectivity by attempting to authenticate and call a simple API.

    Returns:
        tuple: (success: bool, message: str)
    """
    # Check required environment variables
    jira_url = os.getenv('JIRA_URL')
    jira_token = os.getenv('JIRA_TOKEN')

    if not jira_url or not jira_token:
        return False, "Configuration error: JIRA_URL or JIRA_TOKEN not set in environment"

    try:
        # Attempt to create Jira client
        jira = JIRA(server=jira_url, token_auth=jira_token, timeout=10)

        # Make a simple API call to verify connectivity
        # myself() is a lightweight endpoint that returns current user info
        user = jira.myself()

        return True, f"✓ Jira connectivity verified (authenticated as {user.get('displayName', 'unknown')})"

    except Exception as e:
        error_msg = str(e)

        # Provide helpful error messages based on exception type
        if "timeout" in error_msg.lower():
            return False, "✗ Jira connection timeout - VPN may be disconnected"
        elif "unauthorized" in error_msg.lower() or "401" in error_msg:
            return False, "✗ Jira authentication failed - check JIRA_TOKEN"
        elif "connection" in error_msg.lower() or "network" in error_msg.lower():
            return False, "✗ Jira unreachable - ensure VPN is connected"
        else:
            return False, f"✗ Jira connectivity check failed: {error_msg}"

def main():
    """Main entry point for the connectivity checker."""
    print("Checking Jira connectivity...", flush=True)

    success, message = check_jira_connectivity()
    print(message, flush=True)

    if success:
        sys.exit(0)  # Success
    else:
        # Determine exit code based on error type
        if "Configuration error" in message:
            sys.exit(2)  # Configuration error
        else:
            sys.exit(1)  # Connectivity error

if __name__ == "__main__":
    # Load environment variables from .env file if running directly
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # dotenv not required if env vars already set
# Load secrets from macOS Keychain (JIRA_TOKEN was migrated from .env)                                                                                                                                                              
    try:                                                                                                                                                                                                                                
      import keyring                                                                                                                                                                                                                
      token = keyring.get_password("sas-jira", "JIRA_TOKEN")                                                                                                                                                                   
      if token:                                                                                                                                                                                                                
        os.environ["JIRA_TOKEN"] = token                                                                                                                                                                                     
    except Exception:                                                                                                                                                                                                            
      pass  # Fall through; main() will report missing env vars 
    
    main()
