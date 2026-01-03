from abc import ABC, abstractmethod


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
