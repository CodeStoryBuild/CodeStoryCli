"""
Custom exception hierarchy for the dslate CLI application.

This module defines a comprehensive exception hierarchy that provides
clear error messages and proper error categorization for better
error handling and user experience.
"""


class dslateError(Exception):
    """
    Base exception for all dslate-related errors.

    All dslate-specific exceptions should inherit from this class
    to enable consistent error handling throughout the application.
    """

    def __init__(self, message: str, details: str = None):
        """
        Initialize a dslateError.

        Args:
            message: Main error message for the user
            details: Additional technical details for logging
        """
        self.message = message
        self.details = details
        super().__init__(message)


class GitError(dslateError):
    """
    Errors related to git operations.

    Raised when git commands fail or when git repository
    state is invalid for the requested operation.
    """

    pass


class DetachedHeadError(GitError):
    """Raised when on a detached HEAD."""

    pass


class ValidationError(dslateError):
    """
    Input validation errors.

    Raised when user input fails validation checks,
    such as invalid file paths, malformed commit hashes, etc.
    """

    pass


class ConfigurationError(dslateError):
    """
    Configuration-related errors.

    Raised when configuration files are invalid, missing,
    or contain incompatible settings.
    """

    pass


class AIServiceError(dslateError):
    """
    AI service related errors.

    Raised when AI API calls fail, timeout, or return
    invalid responses.
    """

    pass


class FileSystemError(dslateError):
    """
    File system operation errors.

    Raised when file or directory operations fail,
    such as permission issues or missing files.
    """

    pass


class ChunkingError(dslateError):
    """
    Errors during diff chunking operations.

    Raised when the chunking process encounters
    invalid diffs or fails to parse changes.
    """

    pass


class SynthesizerError(dslateError):
    """
    Errors during commit synthesis.

    Raised when the commit synthesis process fails
    to create valid commits from chunks.
    """

    pass


class FixCommitError(dslateError):
    """
    Errors during fix command run
    """

    pass


# Convenience functions for creating common errors
def git_not_found() -> GitError:
    """Create a GitError for when git is not available."""
    return GitError(
        "Git is not installed or not in PATH",
        "Please install git and ensure it's available in your PATH environment variable",
    )


def not_git_repository(path: str = ".") -> GitError:
    """Create a GitError for when not in a git repository."""
    return GitError(
        f"Not a git repository: {path}",
        "Run 'git init' to initialize a git repository or navigate to an existing repository",
    )


def invalid_commit_hash(commit_hash: str) -> ValidationError:
    """Create a ValidationError for invalid commit hashes."""
    return ValidationError(
        f"Invalid commit hash: {commit_hash}",
        "Commit hashes must be 4-40 hexadecimal characters",
    )


def path_not_found(path: str) -> ValidationError:
    """Create a ValidationError for non-existent paths."""
    return ValidationError(
        f"Path not found: {path}",
        "Please check that the path exists and is accessible",
    )


def api_key_missing(service: str) -> ConfigurationError:
    """Create a ConfigurationError for missing API keys."""
    return ConfigurationError(
        f"Missing API key for {service}",
        "Set the API key using environment variable or run setup command",
    )


def ai_service_timeout(service: str, timeout: int) -> AIServiceError:
    """Create an AIServiceError for API timeouts."""
    return AIServiceError(
        f"AI service '{service}' timed out after {timeout} seconds",
        "Try again or increase the timeout setting in configuration",
    )
