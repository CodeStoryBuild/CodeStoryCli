from abc import ABC, abstractmethod
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import ChunkApplicationData


class DiffChunk(ABC):
    """
    Represents a single diff chunk.

    Responsibilities:
    - Must contain enough information to reconstruct a patch for Git
    - Preserves file path, line numbers, and content
    - Can be serialized into a unified diff format
    """

    @abstractmethod
    def format_json(self) -> str:
        """
        Converts a structured diff object into a standardized JSON format
        optimized for LLM comprehension.

        Args:
            file_path: The path of the file being modified.
            change_list: The list of changes in the diff chunk object.

        Returns:
            A JSON string representing the structured diff.
        """

    @abstractmethod
    def get_chunk_application_data(self) -> List["ChunkApplicationData"]:
        """
        Returns the chunk application data needed for applying this chunk's changes.

        This encapsulates the logic for converting the chunk's internal representation
        into the format needed by the GitSynthesizer to apply changes to files.

        Returns:
            A list of ChunkApplicationData objects representing the changes to apply.
        """

    @abstractmethod
    def file_path(self):
        """
        Returns the file path that these changes are linked to
        """
