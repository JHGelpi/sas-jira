# jira_server/logging_config.py
"""
Centralized logging configuration for the SAS-Jira project.

This module sets up logging based on log_config.yaml and provides
a single setup_logging() function that should be called once at
application startup.

DO NOT call logging.basicConfig() in individual modules.
Instead, use: from logging_utils import get_logger
"""

import os
import yaml
import logging
import logging.config
from pathlib import Path


def setup_logging(config_path: str = None, default_level: int = logging.INFO):
    """
    Set up logging configuration for the application.
    
    This function should be called ONCE at application startup (e.g., in main.py).
    Individual modules should NOT call this function or logging.basicConfig().
    
    Args:
        config_path: Path to the YAML logging configuration file.
                    If None, looks for log_config.yaml in the same directory.
        default_level: Default logging level if config file is not found.
    
    Example:
        # In main.py or at application startup
        from logging_config import setup_logging
        setup_logging()
        
        # In any other module
        from logging_utils import get_logger
        logger = get_logger(__name__)
        logger.info("Module started")
    """
    # Determine config file path
    if config_path is None:
        config_path = Path(__file__).parent / 'log_config.yaml'
    else:
        config_path = Path(config_path)
    
    # Ensure the logs directory exists
    log_dir = Path(__file__).parent / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Try to load configuration from YAML
    if config_path.exists():
        try:
            with open(config_path, 'rt', encoding='utf-8') as f:
                config = yaml.safe_load(f.read())
            
            # Apply the configuration
            logging.config.dictConfig(config)
            
            # Log success using standard logging (before our wrapper is available)
            logger = logging.getLogger(__name__)
            logger.info("=" * 80)
            logger.info("Logging configured successfully from log_config.yaml")
            logger.info("=" * 80)
            
        except Exception as e:
            # Fallback to basic config if YAML loading fails
            logging.basicConfig(
                level=default_level,
                format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to load logging configuration from YAML: {e}")
            logger.warning("Fell back to basic logging configuration.")
    else:
        # Fallback if config file is missing
        logging.basicConfig(
            level=default_level,
            format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        logger = logging.getLogger(__name__)
        logger.warning(f"log_config.yaml not found at {config_path}. Using basic logging configuration.")


def get_logger_for_module(module_name: str):
    """
    DEPRECATED: Use logging_utils.get_logger() instead.
    
    This function is kept for backward compatibility but will be removed.
    
    Args:
        module_name: The name of the module (typically __name__)
    
    Returns:
        A standard Python logger (not the enhanced StandardizedLogger)
    """
    import warnings
    warnings.warn(
        "get_logger_for_module() is deprecated. Use 'from logging_utils import get_logger' instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return logging.getLogger(module_name)


# For backward compatibility, allow importing setup_logging from here
__all__ = ['setup_logging', 'get_logger_for_module']
