# vibe/core/data/empty_file_chunk.py

from dataclasses import dataclass
from typing import List, TYPE_CHECKING
import json
from .diff_chunk import DiffChunk

if TYPE_CHECKING:
    from .models import ChunkApplicationData


@dataclass
class EmptyFileAdditionChunk(DiffChunk):
    """
    Represents the addition of an empty file (e.g., empty __init__.py).
    This is a special case that doesn't involve patch application.
    """

    _file_path: str
    file_mode: str = "100644"  # Default to regular file mode

    def file_path(self) -> str:
        return self._file_path

    def format_json(self) -> str:
        """Return JSON describing this empty file addition."""
        return json.dumps(
            {
                "operation": "add_empty_file",
                "file_path": self._file_path,
                "file_mode": self.file_mode,
                "description": f"Create empty file: {self._file_path}",
            }
        )

    def get_chunk_application_data(self) -> List["ChunkApplicationData"]:
        """Empty file additions don't use chunk application data."""
        return []

    def __repr__(self) -> str:
        return f"EmptyFileAdditionChunk(file_path={self._file_path}, file_mode={self.file_mode})"
