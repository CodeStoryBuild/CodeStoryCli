from dataclasses import dataclass
from typing import List

from .chunk import Chunk
from ..grouper.interface import Groupable


@dataclass(frozen=True)
class CompositeDiffChunk(Groupable):
    """
    Represents a composite diff chunk that contains multiple DiffChunk instances.

    This allows grouping multiple related chunks together while maintaining the ability
    to process them as a single logical unit.

    Attributes:
        chunks: List of DiffChunk objects that make up this composite chunk
    """

    chunks: List[Chunk]

    def __post_init__(self):
        if len(self.chunks) <= 0:
            raise RuntimeError("Chunks must be a nonempty list!")

    def format_json(self) -> str:
        """
        Formats all child chunks as JSON, separated by newlines.

        Returns:
            A JSON string representing all child chunks.
        """
        return "\n".join([chunk.format_json() for chunk in self.chunks])

    def canonical_paths(self):
        """
        Return the canonical paths for this composite chunk.

        The composite chunk delegates to its first child chunk for the canonical
        paths. This mirrors the behaviour in other composite/groupable types
        where the first chunk is considered the representative.
        """
        paths = []

        for chunk in self.chunks:
            paths.extend(chunk.canonical_paths())

        return list(set(paths))

    def hunk_ranges(self) -> dict[str, list[tuple[int, int, int, int]]]:
        """
        Aggregate hunk ranges from all child chunks.

        Returns a dict keyed by canonical path (string) with lists of tuples
        describing (old_start, old_len, new_start, new_len). If multiple
        child chunks reference the same path, their ranges are concatenated.
        """
        aggregated: dict[str, list[tuple[int, int, int, int]]] = {}
        for chunk in self.chunks:
            for path, path_ranges in chunk.hunk_ranges().items():
                aggregated.setdefault(path, []).extend(path_ranges)

        return aggregated

    def get_chunks(self) -> list:
        chunks = []
        for chunk in self.chunks:
            chunks.extend(chunk.get_chunks())

        return chunks

