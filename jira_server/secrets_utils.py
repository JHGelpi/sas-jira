"""
Secrets management via macOS Keychain.

Reads secrets from the macOS Keychain using the `keyring` library and injects
them into os.environ so all existing os.getenv() calls work unchanged.
"""

import os
import keyring
from logging_utils import get_logger

logger = get_logger(__name__)

KEYCHAIN_SERVICE = "sas-jira"

SECRET_KEYS = ["JIRA_TOKEN", "DB_PASSWORD", "LDAP_PASS"]


def load_secrets():
    """
    Load secrets from macOS Keychain and inject into os.environ.

    Also constructs DATABASE_URL from component env vars (DB_HOST, DB_USER,
    DB_NAME from .env) plus DB_PASSWORD from Keychain.

    Raises RuntimeError if any secret is missing from the Keychain.
    """
    missing = []

    for key in SECRET_KEYS:
        value = keyring.get_password(KEYCHAIN_SERVICE, key)
        if value:
            os.environ[key] = value
            logger.info(f"Loaded secret '{key}' from macOS Keychain")
        else:
            missing.append(key)
            logger.error(f"Secret '{key}' not found in macOS Keychain")

    if missing:
        raise RuntimeError(
            f"Missing secrets in macOS Keychain: {', '.join(missing)}. "
            f"Run 'python3 setup_keychain.py' to store them."
        )

    logger.success("All secrets loaded from macOS Keychain")


def build_database_url():
    """
    Construct DATABASE_URL from component environment variables and set it
    in os.environ. Expects DB_PASSWORD to already be in os.environ (via
    load_secrets()) and DB_HOST, DB_USER, DB_NAME to come from .env.
    """
    db_host = os.getenv("DB_HOST", "localhost")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_name = os.getenv("DB_NAME")

    if not all([db_user, db_password, db_name]):
        raise RuntimeError(
            "Cannot construct DATABASE_URL: missing DB_USER, DB_PASSWORD, or DB_NAME. "
            "Check .env and Keychain configuration."
        )

    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:5432/{db_name}"
    os.environ["DATABASE_URL"] = database_url
    logger.info("Constructed DATABASE_URL from component variables")
