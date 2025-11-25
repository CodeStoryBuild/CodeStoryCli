from collections.abc import Callable
from dataclasses import dataclass

from .chunk import Chunk
from .immutable_chunk import ImmutableChunk


@dataclass
class CommitGroup:
    """
    A collection of DiffChunks that are committed together.
    """

    chunks: list[Chunk | ImmutableChunk]
    group_id: str
    # branch_name: str
    commit_message: str
    extended_message: str | None = None
