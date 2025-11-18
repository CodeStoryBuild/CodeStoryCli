from abc import ABC, abstractmethod
from pathlib import Path


class GitInterface(ABC):
    """
    Abstract interface for running git commands.
    This abstracts away the details of how git commands are executed.
    """

    @abstractmethod
    def run_git_text(
        self,
        args: list[str],
        input_text: str | None = None,
        env: dict | None = None,
        cwd: str | Path | None = None,
    ) -> str | None:
        """Run a git command with text input/output. Returns None on error."""

    @abstractmethod
    def run_git_binary(
        self,
        args: list[str],
        input_bytes: bytes | None = None,
        env: dict | None = None,
        cwd: str | Path | None = None,
    ) -> bytes | None:
        """Run a git command with binary input/output. Returns None on error."""
