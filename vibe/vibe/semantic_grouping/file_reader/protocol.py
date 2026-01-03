from typing import Protocol

class FileReader(Protocol):
    """An interface for reading file content."""
    def read(self, path: str, old_content: bool = False) -> str | None:
        """
        Reads the content of a file.

        Args:
            path: The canonical path to the file.
            old_content: If True, read the 'before' version of the file.
                         If False, read the 'after' version.

        Returns:
            The file content as a string, or None if it doesn't exist
            (e.g., reading the 'old' version of a newly added file).
        """
        ...