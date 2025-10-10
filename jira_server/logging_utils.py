# jira_server/logging_utils.py
"""
Centralized logging utility for the SAS-Jira project.

This module provides a standardized way to get loggers across all modules,
ensuring consistent formatting, behavior, and emoji usage.

Usage:
    from logging_utils import get_logger
    
    logger = get_logger(__name__)
    logger.info("Starting process...")
    logger.success("Process completed successfully")
    logger.error("An error occurred")
"""

import logging
import sys
import os
from typing import Optional

# ANSI color codes for terminal output (optional, can be disabled)
class Colors:
    """ANSI color codes for prettier terminal output."""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    # Standard colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Bright colors
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'

# Emoji constants (can be toggled on/off)
class Emoji:
    """Standardized emoji set for log messages."""
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    SEARCH = "🔍"
    ROCKET = "🚀"
    GEAR = "⚙️"
    PARTY = "🎉"
    CHART = "📊"
    DATABASE = "💾"
    NETWORK = "🌐"
    LOCK = "🔒"
    KEY = "🔑"
    DOCUMENT = "📄"
    FOLDER = "📁"
    BUG = "🐛"
    WRENCH = "🔧"
    HOURGLASS = "⏳"
    CLOCK = "🕐"
    ARROW_RIGHT = "➡️"
    ARROW_DOWN = "⬇️"
    ARROW_UP = "⬆️"
    CHECK = "✓"
    CROSS = "✗"
    BULLET = "•"
    COMMENT = "💬"
    LABEL = "🏷️"


class StandardizedLogger:
    """
    Wrapper around Python's logging.Logger to provide standardized methods
    with consistent emoji and formatting.
    """
    
    def __init__(self, logger: logging.Logger, use_emoji: bool = True, use_colors: bool = False):
        self._logger = logger
        self.use_emoji = use_emoji
        self.use_colors = use_colors and sys.stdout.isatty()
    
    def _format_message(self, message: str, emoji: Optional[str] = None, color: Optional[str] = None) -> str:
        """Format a message with optional emoji and color."""
        parts = []
        
        if self.use_colors and color:
            parts.append(color)
        
        if self.use_emoji and emoji:
            parts.append(emoji)
        
        parts.append(message)
        
        if self.use_colors and color:
            parts.append(Colors.RESET)
        
        return " ".join(parts)
    
    # Standard logging methods
    def debug(self, message: str, *args, **kwargs):
        """Log a debug message."""
        self._logger.debug(self._format_message(message), *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        """Log an info message."""
        self._logger.info(self._format_message(message, Emoji.INFO, Colors.BLUE), *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """Log a warning message."""
        self._logger.warning(self._format_message(message, Emoji.WARNING, Colors.YELLOW), *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """Log an error message."""
        self._logger.error(self._format_message(message, Emoji.ERROR, Colors.RED), *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs):
        """Log a critical message."""
        self._logger.critical(self._format_message(message, Emoji.ERROR, Colors.BRIGHT_RED), *args, **kwargs)
    
    def exception(self, message: str, *args, **kwargs):
        """Log an exception with traceback."""
        self._logger.exception(self._format_message(message, Emoji.ERROR, Colors.RED), *args, **kwargs)
    
    # Custom convenience methods with standardized emoji
    def success(self, message: str, *args, **kwargs):
        """Log a success message."""
        self._logger.info(self._format_message(message, Emoji.SUCCESS, Colors.GREEN), *args, **kwargs)
    
    def start(self, message: str, *args, **kwargs):
        """Log the start of an operation."""
        self._logger.info(self._format_message(message, Emoji.ROCKET, Colors.CYAN), *args, **kwargs)
    
    def complete(self, message: str, *args, **kwargs):
        """Log the completion of an operation."""
        self._logger.info(self._format_message(message, Emoji.PARTY, Colors.GREEN), *args, **kwargs)
    
    def connecting(self, message: str, *args, **kwargs):
        """Log a connection attempt."""
        self._logger.info(self._format_message(message, Emoji.GEAR, Colors.CYAN), *args, **kwargs)
    
    def searching(self, message: str, *args, **kwargs):
        """Log a search operation."""
        self._logger.info(self._format_message(message, Emoji.SEARCH, Colors.BLUE), *args, **kwargs)
    
    def processing(self, message: str, *args, **kwargs):
        """Log a processing step."""
        self._logger.info(self._format_message(message, Emoji.ARROW_RIGHT, Colors.BLUE), *args, **kwargs)
    
    def database(self, message: str, *args, **kwargs):
        """Log a database operation."""
        self._logger.info(self._format_message(message, Emoji.DATABASE, Colors.MAGENTA), *args, **kwargs)
    
    def skip(self, message: str, *args, **kwargs):
        """Log a skipped operation."""
        self._logger.info(self._format_message(message, Emoji.ARROW_RIGHT, Colors.YELLOW), *args, **kwargs)
    
    # Delegate other attributes to the underlying logger
    def __getattr__(self, name):
        return getattr(self._logger, name)


# Global configuration
_USE_EMOJI = os.getenv('LOG_USE_EMOJI', 'true').lower() in ('true', '1', 'yes')
_USE_COLORS = os.getenv('LOG_USE_COLORS', 'false').lower() in ('true', '1', 'yes')


def configure_logging(use_emoji: bool = True, use_colors: bool = False):
    """
    Configure global logging preferences.
    
    Args:
        use_emoji: Whether to include emoji in log messages (default: True)
        use_colors: Whether to use ANSI colors in terminal output (default: False)
    """
    global _USE_EMOJI, _USE_COLORS
    _USE_EMOJI = use_emoji
    _USE_COLORS = use_colors


def get_logger(name: str) -> StandardizedLogger:
    """
    Get a standardized logger for a module.
    
    This function should be used instead of directly calling logging.getLogger()
    to ensure consistent behavior across all modules.
    
    Args:
        name: The name of the logger (typically __name__)
    
    Returns:
        A StandardizedLogger instance
    
    Example:
        logger = get_logger(__name__)
        logger.info("Starting process...")
        logger.success("Process completed!")
    """
    base_logger = logging.getLogger(name)
    return StandardizedLogger(base_logger, use_emoji=_USE_EMOJI, use_colors=_USE_COLORS)


def log_section_header(logger: StandardizedLogger, title: str, width: int = 80):
    """
    Log a formatted section header for better readability in logs.
    
    Args:
        logger: The logger to use
        title: The section title
        width: The width of the header line (default: 80)
    
    Example:
        log_section_header(logger, "DATABASE SYNC")
    """
    separator = "=" * width
    logger.info(separator)
    logger.info(f"{title.center(width)}")
    logger.info(separator)


def log_subsection_header(logger: StandardizedLogger, title: str, width: int = 80):
    """
    Log a formatted subsection header.
    
    Args:
        logger: The logger to use
        title: The subsection title
        width: The width of the header line (default: 80)
    """
    separator = "-" * width
    logger.info(separator)
    logger.info(f"  {title}")
    logger.info(separator)