# -----------------------------------------------------------------------------
# /*
#  * Copyright (C) 2025 CodeStory
#  *
#  * This program is free software; you can redistribute it and/or modify
#  * it under the terms of the GNU General Public License as published by
#  * the Free Software Foundation; Version 2.
#  *
#  * This program is distributed in the hope that it will be useful,
#  * but WITHOUT ANY WARRANTY; without even the implied warranty of
#  * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  * GNU General Public License for more details.
#  *
#  * You should have received a copy of the GNU General Public License
#  * along with this program; if not, you can contact us at support@codestory.build
#  */
# -----------------------------------------------------------------------------

"""Enhanced logging configuration for the codestory CLI application.

This module provides structured logging with proper formatting, log
levels, and file management for better observability and debugging.
"""

import os
from datetime import datetime
from pathlib import Path

from codestory.constants import LOG_DIR

LOG_DIR.mkdir(parents=True, exist_ok=True)


class StructuredLogger:
    """Structured logging helper for consistent log formatting."""

    def __init__(
        self,
        command_name: str,
        debug: bool = False,
        silent: bool = False,
        no_log_files: bool = False,
    ):
        self.command_name = command_name
        self.debug = debug
        self.silent = silent
        self.no_log_files = no_log_files
        self._setup_logger()

    def _setup_logger(self) -> None:
        """Set up loguru with proper formatting and sinks."""
        from loguru import logger

        # Clear existing sinks to avoid duplicates
        logger.remove()

        # Determine log level - flags override env vars
        if self.debug:
            log_level = "DEBUG"
            console_level = "DEBUG"
        elif self.silent:
            log_level = "ERROR"
            console_level = "ERROR"
        else:
            log_level = os.getenv("CODESTORY_LOG_LEVEL", "INFO").upper()
            console_level = os.getenv("CODESTORY_CONSOLE_LOG_LEVEL", log_level).upper()

        # Create timestamped log file
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        logfile = LOG_DIR / f"codestory_{timestamp}.log"

        # Console sink with simple formatting
        def console_sink(message):
            from tqdm import tqdm

            from codestory.core.logging.progress_manager import ProgressBarManager

            text = message.record["message"].rstrip("\n")
            if ProgressBarManager.is_active():
                tqdm.write(text)
            else:
                print(text)

        # Add console sink with appropriate level
        logger.add(console_sink, level=console_level, format="{message}", catch=True)

        if self.no_log_files:
            self.logfile = None
            logger.debug("File logging disabled")
            return

        # File sink with detailed formatting
        logger.add(
            logfile,
            level="DEBUG",
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>",
            rotation="10 MB",
            retention="14 days",
            compression="gz",
            catch=True,
            backtrace=True,
            diagnose=True,
        )

        # Log initialization
        logger.bind(
            command=self.command_name, logfile=str(logfile), log_level=log_level
        ).debug("Logger initialized")

        logger.debug(f"Log File Created At: {logfile}")

        self.logfile = logfile

    def get_logfile(self) -> Path | None:
        """Get the current log file path."""
        return self.logfile


def setup_logger(
    command_name: str,
    debug: bool = False,
    silent: bool = False,
    no_log_files: bool = False,
) -> Path | None:
    """Set up enhanced logging for a command.

    Args:
        command_name: Name of the command being executed
        debug: Enable debug logging
        silent: Suppress most console output (only errors)
        no_log_files: Disable logging to files

    Returns:
        Path to the log file, or None if file logging is disabled
    """
    structured_logger = StructuredLogger(
        command_name, debug=debug, silent=silent, no_log_files=no_log_files
    )
    return structured_logger.get_logfile()


def setup_debug_logging() -> None:
    """Enable debug logging for troubleshooting.

    Note: This creates a new StructuredLogger with debug=True.
    """
    StructuredLogger("debug", debug=True)


def get_log_directory() -> Path:
    """Get the directory where log files are stored."""
    return LOG_DIR


def cleanup_old_logs(days: int = 14) -> int:
    """Clean up log files older than the specified number of days.

    Args:
        days: Number of days to keep logs

    Returns:
        Number of files cleaned up
    """
    import time

    cutoff_time = time.time() - (days * 24 * 60 * 60)
    cleaned = 0

    for log_file in LOG_DIR.glob("*.log*"):
        if log_file.stat().st_mtime < cutoff_time:
            try:
                log_file.unlink()
                cleaned += 1
            except OSError:
                pass  # File might be in use or permission issues

    return cleaned
