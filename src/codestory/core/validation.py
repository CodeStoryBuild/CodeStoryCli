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
"""Input validation utilities for the codestory CLI application.

This module provides comprehensive input validation with clear error
messages and type safety for all CLI parameters and configuration
values.
"""

import os
import re

from codestory.core.exceptions import (
    DetachedHeadError,
    GitError,
    ValidationError,
)
from codestory.core.git.git_commands import GitCommands


def is_root_commit(git_commands: GitCommands, commit_hash: str) -> bool:
    """Check if a commit is a root commit (has no parents).

    Args:
        git_commands: Git commands to run
        commit_hash: The commit hash to check

    Returns:
        True if it's a root commit, False otherwise
    """
    return git_commands.try_get_parent_hash(commit_hash) is None


def validate_commit_hash(
    value: str, git_commands: GitCommands | None = None, branch: str | None = None
) -> str:
    """Validate and normalize a git commit hash. If `value` is the string "HEAD", and a
    `git_commands` and `branch` are provided, resolve it by running `git rev-parse
    <branch>` and return the resolved commit hash.

    Args:
        value: The commit hash string to validate
        git_commands: Optional GitCommands to resolve symbolic refs like HEAD
        branch: Optional branch name to resolve HEAD against

    Returns:
        The normalized (lowercase) commit hash or the raw resolved hash

    Raises:
        ValidationError: If the commit hash format is invalid
    """
    if value == "HEAD":
        # Resolve HEAD relative to the provided branch if possible
        if git_commands is not None and branch:
            try:
                return git_commands.get_commit_hash(branch)
            except ValueError:
                raise ValidationError(f"Failed to resolve branch: {branch}")
        # If no branch given but git_commands is provided, fall back to rev-parse HEAD
        if git_commands is not None:
            try:
                return git_commands.get_commit_hash("HEAD")
            except ValueError:
                raise ValidationError("Failed to resolve HEAD")
        raise ValidationError("HEAD is ambiguous without a repository context")

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


def validate_target_path(value: str | list[str] | None) -> list[str] | None:
    """Validate that target paths are valid strings. Git pathspecs are flexible, so we
    primarily ensure they are non-empty strings.

    Args:
        value: The path string or list of path strings to validate

    Returns:
        A list of validated path strings or None

    Raises:
        ValidationError: If any path is invalid
    """
    if value is None:
        # using no target
        return None

    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = value
    else:
        raise ValidationError("Target path must be a string or a list of strings")

    if not values:
        return None

    for v in values:
        if not v or not isinstance(v, str):
            raise ValidationError("Target path cannot be empty")

    return values


def validate_message_length(value: str | None) -> str | None:
    """Validate commit message length and content.

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
    """Validate ignore patterns for commit hashes.

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
    """Validate minimum size parameter.

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


def validate_git_repository(git_commands: GitCommands) -> None:
    """Validate that we're in a git repository and that the current directory is the
    repository root.

    Args:
        git_commands: Git commands to run

    Raises:
        GitError: If git is not available, not in a repository, or not at the root
    """
    # Check if git is available and we're inside a work tree
    if not git_commands.is_git_repo():
        # Keep error message compatible with existing tests
        raise GitError("Not a git repository")

    # Ensure the current directory is the repository root
    repo_root = git_commands.get_repo_root()
    if not repo_root:
        raise GitError("Not a git repository")

    try:
        # Normalize paths for comparison (especially on Windows)
        cwd = os.path.abspath(os.getcwd())
        root = os.path.abspath(repo_root)

        if cwd.lower() != root.lower() if os.name == "nt" else cwd != root:
            raise GitError("Not a git repository")
    except (OSError, ValueError):
        raise GitError("Not a git repository")


def validate_default_branch(git_commands: GitCommands) -> None:
    """Validate that we are on a branch (not in detached HEAD state).

    Args:
        git_commands: Git commands to run

    Raises:
        DetachedHeadError: If in detached HEAD state
        GitError: If failed to check branch status
    """
    # validate that we are on a branch
    branch_name = git_commands.get_show_current_branch()

    # check that not a detached branch
    if not branch_name:
        msg = "Operation failed: You are in 'detached HEAD' state."
        raise DetachedHeadError(msg)


def validate_branch(git_commands: GitCommands, branch_name: str) -> None:
    """Validate that a branch exists in the repository.

    Args:
        git_commands: Git commands to run
        branch_name: The branch name to validate

    Raises:
        ValidationError: If the branch does not exist
    """
    try:
        git_commands.get_commit_hash(branch_name)
    except ValueError:
        raise ValidationError(f"Branch '{branch_name}' does not exist.")


def validate_no_merge_commits_in_range(
    git_commands: GitCommands, start_commit: str, end_ref: str
) -> None:
    """Validate that there are no merge commits in the range from start_commit to
    end_ref.

    Args:
        git_commands: Git commands to run
        start_commit: The starting commit hash (exclusive)
        end_ref: The ending reference (inclusive)

    Raises:
        ValidationError: If any merge commits are found in the range
    """
    # Use --merges flag to efficiently find only merge commits in the range
    merge_commits = git_commands.get_rev_list(
        f"{start_commit}..{end_ref}", merges=True, n=1
    )

    if merge_commits:
        # Found at least one merge commit
        merge_commit = merge_commits[0]
        raise ValidationError(
            f"Merge commit detected: {merge_commit[:7]}",
            f"Cannot rewrite history that contains merge commits. "
            f"The range {start_commit[:7]}..{end_ref[:7]} contains merge commits.",
        )


def sanitize_user_input(user_input: str, max_length: int = 1000) -> str:
    """Sanitize user input to prevent security issues.

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
