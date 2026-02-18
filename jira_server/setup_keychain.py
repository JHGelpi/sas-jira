#!/usr/bin/env python3
"""
One-time setup script to store secrets in macOS Keychain.

Usage:
    python3 setup_keychain.py
"""

import getpass
import keyring

KEYCHAIN_SERVICE = "sas-jira"

SECRETS = [
    ("JIRA_TOKEN", "Jira Personal Access Token"),
    ("DB_PASSWORD", "PostgreSQL database password"),
    ("LDAP_PASS", "LDAP password"),
]


def main():
    print(f"Storing secrets in macOS Keychain (service: '{KEYCHAIN_SERVICE}')\n")

    for key, description in SECRETS:
        current = keyring.get_password(KEYCHAIN_SERVICE, key)
        if current:
            print(f"  [{key}] Already set in Keychain.")
            update = input(f"    Overwrite? (y/N): ").strip().lower()
            if update != "y":
                print(f"    Skipped.\n")
                continue

        value = getpass.getpass(f"  Enter {description} ({key}): ")
        if not value:
            print(f"    Empty value, skipped.\n")
            continue

        keyring.set_password(KEYCHAIN_SERVICE, key, value)

        # Verify the stored value
        stored = keyring.get_password(KEYCHAIN_SERVICE, key)
        if stored == value:
            print(f"    Stored and verified.\n")
        else:
            print(f"    WARNING: Verification failed for {key}.\n")

    print("Done. Secrets are stored in macOS Keychain.")
    print("You can now remove secret values from .env if present.")


if __name__ == "__main__":
    main()
