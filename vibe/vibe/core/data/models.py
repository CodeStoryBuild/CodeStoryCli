from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class CommitGroup:
    """
    A collection of DiffChunks that are committed together.
    """

    chunks: list["Chunk"]
    group_id: str
    # branch_name: str
    commit_message: str
    extended_message: str | None = None


@dataclass
class CommitResult:
    """
    Result of a commit operation.
    """

    commit_hash: str
    group: CommitGroup


ProgressCallback = Callable[[int], None]
