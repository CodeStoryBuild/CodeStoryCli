"""
CommitterInterface

This interface is responsible for creating commits from grouped chunks.

Responsibilities:
- Accept ChunkGroup objects and commit them via GitInterface
- Generate descriptive commit messages (optionally AI-assisted)
- Return a CommitResult object containing commit hash and metadata

Possible Implementations:
- StandardCommitter: basic commit using a given message
- AICommitter: generates commit messages automatically
- HybridCommitter: AI generates a message, user confirms

Notes:
- Should handle staging of chunks/files before committing
- Supports optional branching or pushing strategies
- Enables fully modular commit creation, including metadata or tags
"""

from abc import ABC, abstractmethod
from typing import List
from ..data.models import ChunkGroup, CommitResult
from ..git_interface.interface import GitInterface

class CommitterInterface(ABC):
    @abstractmethod
    def create_commit(self, group: ChunkGroup, git_interface: GitInterface) -> CommitResult:
        """Create a commit from grouped chunks, return CommitResult"""
