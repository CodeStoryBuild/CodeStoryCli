from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Union

class GitInterface(ABC):
    """
    Abstract interface for running git commands.
    This abstracts away the details of how git commands are executed.
    """

    @abstractmethod
    def run_git_text(self, args: List[str], input_text: Optional[str] = None, env: Optional[Dict] = None) -> str:
        """Run a git command with text input/output."""

    @abstractmethod
    def run_git_binary(self, args: List[str], input_bytes: Optional[bytes] = None, env: Optional[Dict] = None) -> bytes:
        """Run a git command with binary input/output."""
