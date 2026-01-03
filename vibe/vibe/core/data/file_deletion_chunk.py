# vibe/core/data/file_deletion_chunk.py

from dataclasses import dataclass
from typing import List, TYPE_CHECKING
import json
from .diff_chunk import DiffChunk

if TYPE_CHECKING:
    from .models import ChunkApplicationData


@dataclass
class FileDeletionChunk(DiffChunk):
    """
    Represents the deletion of a file.
    This is a special case that requires 'git rm' rather than patch application.
    """

    _file_path: str

    def file_path(self) -> str:
        return self._file_path

    def format_json(self) -> str:
        """Return JSON describing this file deletion."""
        return json.dumps(
            {
                "operation": "delete_file",
                "file_path": self._file_path,
                "description": f"Delete file: {self._file_path}",
            }
        )

    def get_chunk_application_data(self) -> List["ChunkApplicationData"]:
        """File deletions don't use chunk application data."""
        return []

    def __repr__(self) -> str:
        return f"FileDeletionChunk(file_path={self._file_path})"
