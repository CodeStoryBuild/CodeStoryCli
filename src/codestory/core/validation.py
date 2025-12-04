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

"""
Input validation utilities for the codestory CLI application.

This module provides comprehensive input validation with clear error messages
and type safety for all CLI parameters and configuration values.
"""

import re
from pathlib import Path

from codestory.core.exceptions import (
    DetachedHeadError,
    FileSystemError,
    GitError,
    ValidationError,
)
from codestory.core.git_interface.interface import GitInterface


def validate_commit_hash(value: str) -> str:
    """
    Validate and normalize a git commit hash.

    Args:
        value: The commit hash string to validate

    Returns:
        The normalized (lowercase) commit hash

    Raises:
        ValidationError: If the commit hash format is invalid
    """
    if not value or not isinstance(value, str):
        raise ValidationError("Commit hash cannot be empty")

    value = value.strip()

    # Git accepts partial hashes (4-40 chars, hex only)
    if not re.match(r"^[a-fA-F0-9]{4,40}$", value):
        raise ValidationError(
            f"Invalid commit hash format: {value}",
            "Commit hashes must be 4-40 hexadecimal characters",
        )

    return value.lower()


def validate_target_path(value: str | None) -> Path:
    """
    Validate that a target path exists and is accessible.

    Args:
        value: The path string to validate

    Returns:
        The validated Path object

    Raises:
        ValidationError: If the path doesn't exist or isn't accessible
        FileSystemError: If there are permission issues
    """
    if value is None:
        # using no target
        return None

    if not value or not isinstance(value, str):
        raise ValidationError("Target path cannot be empty")

    try:
        path = Path(value).resolve()
    except (OSError, ValueError) as e:
        raise ValidationError(f"Invalid path format: {value}") from e

    if not path.exists():
        raise ValidationError(
            f"The specified path does not exist: {value}",
            "Please check that the path is correct and accessible",
        )

    if not (path.is_dir() or path.is_file()):
        raise ValidationError(
            f"Path is not a valid file or directory: {value}",
            "Please specify a valid file or directory path",
        )

    # Check if we have read access
    try:
        if path.is_dir():
            list(path.iterdir())
        else:
            path.read_text()
    except PermissionError as e:
        raise FileSystemError(
            f"Permission denied accessing: {value}",
            "Please check file/directory permissions",
        ) from e
    except UnicodeDecodeError:
        # Binary files are OK, we just can't read them as text
        pass

    return path


def validate_message_length(value: str | None) -> str | None:
    """
    Validate commit message length and content.

    Args:
        value: The commit message to validate (can be None)

    Returns:
        The trimmed commit message or None

    Raises:
        ValidationError: If the message is invalid
    """
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValidationError("Commit message must be a string")

    value = value.strip()

    if len(value) == 0:
        raise ValidationError("Commit message cannot be empty")

    if len(value) > 1000:
        raise ValidationError(
            "Commit message is too long (maximum 1000 characters)",
            f"Current length: {len(value)} characters",
        )

    # Check for potentially problematic characters
    if "\x00" in value:
        raise ValidationError(
            "Commit message contains null bytes",
            "Please remove null characters from the message",
        )

    return value


def validate_ignore_patterns(patterns: list[str] | None) -> list[str]:
    """
    Validate ignore patterns for commit hashes.

    Args:
        patterns: List of commit hash patterns to ignore

    Returns:
        List of validated patterns

    Raises:
        ValidationError: If any pattern is invalid
    """
    if patterns is None:
        return []

    if not isinstance(patterns, list):
        raise ValidationError("Ignore patterns must be a list")

    validated_patterns = []
    for i, pattern in enumerate(patterns):
        if not isinstance(pattern, str):
            raise ValidationError(f"Ignore pattern {i} must be a string")

        pattern = pattern.strip()
        if not pattern:
            continue

        # Validate as potential commit hash prefix
        if not re.match(r"^[a-fA-F0-9]+$", pattern):
            raise ValidationError(
                f"Invalid ignore pattern: {pattern}",
                "Patterns must be hexadecimal characters (commit hash prefixes)",
            )

        if len(pattern) > 40:
            raise ValidationError(
                f"Ignore pattern too long: {pattern}",
                "Commit hash patterns cannot exceed 40 characters",
            )

        validated_patterns.append(pattern.lower())

    return validated_patterns


def validate_min_size(value: int | None) -> int | None:
    """
    Validate minimum size parameter.

    Args:
        value: The minimum size value

    Returns:
        The validated size or None

    Raises:
        ValidationError: If the size is invalid
    """
    if value is None:
        return None

    if not isinstance(value, int):
        raise ValidationError("Minimum size must be an integer")

    if value < 1:
        raise ValidationError("Minimum size must be positive", f"Got: {value}")

    if value > 10000:
        raise ValidationError(
            "Minimum size is too large (maximum 10000)", f"Got: {value}"
        )

    return value


def validate_git_repository(git_interface: GitInterface) -> None:
    """
    Validate that we're in a git repository.

    Args:
        path: Path to check for git repository

    Raises:
        GitError: If git is not available or not in a repository
    """
    # Check if git is available
    try:
        git_interface.run_git_text_out(
            ["--version"],
        )
    except NotADirectoryError:
        raise GitError("Current directory is not a git repository")
    except Exception as e:
        raise GitError(
            f"Git version check failed: {e}",
        )
    # Check if we're in a git repository
    is_in_repo = git_interface.run_git_text_out(
        ["rev-parse", "--is-inside-work-tree"],
    )
    if is_in_repo is None or "fatal: not a git repository" in is_in_repo:
        raise GitError("Current directory is not a git repository")

    # validate that we are on a branch
    try:
        original_branch = (
            git_interface.run_git_text_out(["branch", "--show-current"]) or ""
        )
        # check that not a detached branch
        if not original_branch.strip():
            msg = "Operation failed: You are in 'detached HEAD' state."
            raise DetachedHeadError(msg)
    except Exception as e:
        raise GitError(f"Failed to check git branch status: {e}") from e


def sanitize_user_input(user_input: str, max_length: int = 1000) -> str:
    """
    Sanitize user input to prevent security issues.

    Args:
        user_input: The input string to sanitize
        max_length: Maximum allowed length

    Returns:
        The sanitized input string

    Raises:
        ValidationError: If input is invalid
    """
    if not isinstance(user_input, str):
        raise ValidationError("Input must be a string")

    if len(user_input) > max_length:
        raise ValidationError(f"Input too long (max {max_length} characters)")

    # Remove null bytes and non-printable control characters (except newlines/tabs)
    sanitized = "".join(
        char for char in user_input if char.isprintable() or char in "\n\t\r"
    )

    return sanitized.strip()
