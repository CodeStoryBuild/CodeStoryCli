from itertools import groupby
from typing import Optional, List, Union
from dataclasses import dataclass
import json

from loguru import logger

from ..data.line_changes import Addition, Removal
from ..data.hunk_wrapper import HunkWrapper


@dataclass(frozen=True)
class DiffChunk:
    """
    Represents a single diff chunk.

    Responsibilities:
    - Must contain enough information to reconstruct a patch for Git
    - Preserves file path, line numbers, and content
    - Can be serialized into a unified diff format
    """

    # if old path == new path, this is just the file path (no rename, or new addition/deletion)
    # if old path (!None) != new path (!None), this is a rename operation
    # if old path is None and new path is not None, this is a new file addition
    # if old path is not None and new path is None, this is a file deletion
    old_file_path: Optional[bytes] = None
    new_file_path: Optional[bytes] = None

    def canonical_path(self) -> bytes | None:
        """
        Returns the relevant path for the chunk.
        For renames or standard chunks, this is new_file_path
        For additions/deletions, this is the path that is not NONE
        """

        if self.new_file_path is not None:
            return self.new_file_path
        else:
            return self.old_file_path

    @property
    def is_file_rename(self) -> bool:
        return (
            self.old_file_path is not None
            and self.new_file_path is not None
            and self.old_file_path != self.new_file_path
        )

    @property
    def is_standard_modification(self) -> bool:
        return (
            self.old_file_path == self.new_file_path and self.old_file_path is not None
        )

    @property
    def is_file_addition(self) -> bool:
        return self.old_file_path is None and self.new_file_path is not None

    @property
    def is_file_deletion(self) -> bool:
        return self.old_file_path is not None and self.new_file_path is None

    # the file mode from git diff (e.g., b'100644', b'100755')
    file_mode: Optional[bytes] = None
    # whether the chunk should have a "\\ no newline at end of file" at end of the chunk
    contains_newline_fallback: bool = False
    contains_newline_marker: bool = False

    # the structured content of this chunk (list of Addition/Removal objects)
    parsed_content: Optional[List[Union[Addition, Removal]]] = None

    @property
    def has_content(self) -> bool:
        return self.parsed_content is not None and len(self.parsed_content) > 0

    # starting line number in the old file (for patch)
    old_start: Optional[int] = None
    # starting line number in the new file (for patch)
    new_start: Optional[int] = None

    @property
    def line_anchor(self) -> tuple[int | None, int | None]:
        """Return some value to get an idea of where the chunk is anchored."""

        return (self.old_start, self.new_start)

    def old_len(self) -> int:
        if self.parsed_content is None:
            return 0
        return sum(1 for c in self.parsed_content if isinstance(c, Removal))

    def new_len(self) -> int:
        if self.parsed_content is None:
            return 0
        return sum(1 for c in self.parsed_content if isinstance(c, Addition))

    def pure_addition(self) -> bool:
        return self.old_len() == 0 and self.has_content

    def pure_deletion(self) -> bool:
        return self.new_len() == 0 and self.has_content

    def split_into_atomic_chunks(self) -> List["DiffChunk"]:
        """
        Splits a DiffChunk into a list of the most granular, yet still valid,
        atomic DiffChunks.
        """
        # If the chunk has no content (e.g., a file mode change), it is already atomic.
        if not self.has_content:
            return [self]

        # These initial checks are critical for establishing a valid starting point.
        if self.old_start is None or self.new_start is None:
            logger.warning(f"Cannot split chunk with invalid start lines: {self}")
            return [self]

        # only try to be smart and split hunks if its a pure addition or deletion
        # otherwise, things get messy fast
        if not self.pure_addition() or self.pure_deletion():
            return [self]

        final_chunks = []

        if self.parsed_content is not None:
            for line in self.parsed_content:
                atomic_chunk = DiffChunk.from_parsed_content_slice(
                    old_file_path=self.old_file_path,
                    new_file_path=self.new_file_path,
                    file_mode=self.file_mode,
                    contains_newline_fallback=self.contains_newline_fallback,
                    contains_newline_marker=self.contains_newline_marker,
                    parsed_slice=[line],
                )
                final_chunks.append(atomic_chunk)

        return final_chunks

    @staticmethod
    def _sanitize_patch_content(content: bytes) -> bytes:
        """
        Sanitize text for use in a Git patch.
        """
        return content

    @classmethod
    def from_hunk(cls, hunk: HunkWrapper) -> "DiffChunk":
        """
        Construct a DiffChunk from a single, parsed HunkWrapper.
        This is the standard factory for this class.
        """
        parsed_content: List[Union[Addition, Removal]] = []
        current_old_line = hunk.old_start
        current_new_line = hunk.new_start

        contains_newline_fallback = False
        contains_newline_marker = False

        for line in hunk.hunk_lines:
            sanitized_content = DiffChunk._sanitize_patch_content(line[1:])
            if line.startswith(b"+"):
                parsed_content.append(
                    Addition(content=sanitized_content, line_number=current_new_line)
                )
                current_new_line += 1
            elif line.startswith(b"-"):
                parsed_content.append(
                    Removal(content=sanitized_content, line_number=current_old_line)
                )
                current_old_line += 1
            elif line.strip() == b"\\ No newline at end of file":
                contains_newline_marker = True
                if parsed_content:
                    parsed_content[-1].content = (
                        parsed_content[-1].content + b"\n\\ No newline at end of file"
                    )
                else:
                    contains_newline_fallback = True

        return cls(
            new_file_path=hunk.new_file_path,
            old_file_path=hunk.old_file_path,
            file_mode=hunk.file_mode,
            parsed_content=parsed_content,
            old_start=hunk.old_start,
            new_start=hunk.new_start,
            contains_newline_fallback=contains_newline_fallback,
            contains_newline_marker=contains_newline_marker,
        )

    @classmethod
    def from_parsed_content_slice(
        cls,
        old_file_path: Optional[bytes],
        new_file_path: Optional[bytes],
        file_mode: Optional[bytes],
        contains_newline_fallback: bool,
        contains_newline_marker: bool,
        parsed_slice: List[Union[Addition, Removal]],
    ) -> "DiffChunk":
        if not parsed_slice:
            raise ValueError("parsed_slice cannot be empty")

        removals = [item for item in parsed_slice if isinstance(item, Removal)]
        additions = [item for item in parsed_slice if isinstance(item, Addition)]

        if removals and not additions:
            # Pure Deletion
            old_start = removals[0].line_number
            # If the file is being deleted (new_file_path is None), start is 0
            if new_file_path is None:
                new_start = 0
            else:
                new_start = max(0, old_start - 1)

        elif additions and not removals:
            # Pure Addition
            new_start = additions[0].line_number
            # If the file is new (old_file_path is None), start is 0
            if old_file_path is None:
                old_start = 0
            else:
                old_start = max(0, new_start - 1)

        elif removals and additions:
            # Modification (Standard Hunk)
            old_start = removals[0].line_number
            new_start = additions[0].line_number
        else:
            raise ValueError("Invalid input parsed_slice")

        return cls(
            old_file_path=old_file_path,
            new_file_path=new_file_path,
            file_mode=file_mode,
            contains_newline_fallback=contains_newline_fallback,
            contains_newline_marker=contains_newline_marker,
            parsed_content=parsed_slice,
            old_start=old_start,
            new_start=new_start,
        )

    # chunk protocol

    def get_chunks(self) -> list["DiffChunk"]:
        return [self]

    def canonical_paths(self) -> list[bytes | None]:
        """
        Returns the relevant path for the chunk.
        For renames or standard chunks, this is new_file_path
        For additions/deletions, this is the path that is not NONE
        """

        if self.new_file_path is not None:
            return [self.new_file_path]
        else:
            return [self.old_file_path]
