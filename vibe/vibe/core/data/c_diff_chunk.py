from dataclasses import dataclass
from typing import List

from .diff_chunk import DiffChunk
from .s_diff_chunk import StandardDiffChunk
from .models import ChunkApplicationData


@dataclass(frozen=True)
class CompositeDiffChunk(DiffChunk):
    """
    Represents a composite diff chunk that contains multiple StandardDiffChunk instances.

    This allows grouping multiple related chunks together while maintaining the ability
    to process them as a single logical unit.

    Attributes:
        chunks: List of StandardDiffChunk objects that make up this composite chunk
        file_path: The file path for this composite chunk (all child chunks should have the same path)
    """

    chunks: List[StandardDiffChunk]
    _file_path: str

    def format_json(self) -> str:
        """
        Formats all child chunks as JSON, separated by newlines.

        Returns:
            A JSON string representing all child chunks.
        """
        return "\n".join([chunk.format_json() for chunk in self.chunks])

    def get_chunk_application_data(self) -> List[ChunkApplicationData]:
        """
        Returns the application data for all child chunks.

        This method collects the ChunkApplicationData from all child StandardDiffChunk
        instances and returns them as a single flat list.

        Returns:
            A list of ChunkApplicationData objects from all child chunks.
        """
        result = []
        for chunk in self.chunks:
            result.extend(chunk.get_chunk_application_data())
        return result

    def file_path(self):
        return self._file_path
