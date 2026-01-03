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

    def canonical_path(self):
        return self.chunks[0].canonical_path()

    @property
    def old_file_path(self):
        return self.chunks[0].old_file_path

    @property
    def new_file_path(self):
        return self.chunks[0].new_file_path

    @property
    def line_anchor(self):
        return self.chunks[0].line_anchor

    @property
    def is_file_rename(self) -> bool:
        return all(chunk.is_file_rename for chunk in self.chunks)

    @property
    def is_standard_modification(self) -> bool:
        return all(chunk.is_standard_modification for chunk in self.chunks)

    @property
    def is_file_addition(self) -> bool:
        return all(chunk.is_file_addition for chunk in self.chunks)

    @property
    def is_file_deletion(self) -> bool:
        return all(chunk.is_file_deletion for chunk in self.chunks)

    @property
    def has_content(self) -> bool:
        return all(chunk.has_content for chunk in self.chunks)

    @property
    def parsed_content(self) -> List:
        combined = []
        for chunk in self.chunks:
            if chunk.parsed_content:
                combined.extend(chunk.parsed_content)
        return combined
