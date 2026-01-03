from dataclasses import dataclass
from typing import List, Optional, Callable


@dataclass
class CommitGroup:
    """
    A collection of DiffChunks that are committed together.
    """

    chunks: List["Chunk"]
    group_id: str
    # branch_name: str
    commit_message: str
    extended_message: Optional[str] = None


@dataclass
class CommitResult:
    """
    Result of a commit operation.
    """

    commit_hash: str
    group: CommitGroup


ProgressCallback = Callable[[int], None]
