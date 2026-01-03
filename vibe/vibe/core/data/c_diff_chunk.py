from dataclasses import dataclass
from typing import List

from .diff_chunk import DiffChunk
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

    chunks: List[DiffChunk]

    def format_json(self) -> str:
        """
        Formats all child chunks as JSON, separated by newlines.

        Returns:
            A JSON string representing all child chunks.
        """
        return "\n".join([chunk.format_json() for chunk in self.chunks])
