from itertools import groupby
from typing import Optional, List, Union
from dataclasses import dataclass
import json

from loguru import logger

from ..data.line_changes import Addition, Removal
from ..data.hunk_wrapper import HunkWrapper
from ..data.utils import format_content_json
from ..grouper.interface import Groupable


@dataclass(frozen=True)
class DiffChunk(Groupable):
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
    old_file_path: Optional[str] = None
    new_file_path: Optional[str] = None

    def canonical_path(self):
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

    # the file mode from git diff (e.g., '100644', '100755')
    file_mode: Optional[str] = None
    # the structured content of this chunk (list of Addition/Removal objects)
    parsed_content: Optional[List[Union[Addition, Removal]]] = None

    @property
    def has_content(self) -> bool:
        return len(self.parsed_content) > 0

    # starting line number in the old file (for patch)
    old_start: Optional[int] = None
    # starting line number in the new file (for patch)
    new_start: Optional[int] = None

    @property
    def line_anchor(self):
        """Return some value to get an idea of where the chunk is anchored."""

        return (self.old_start, self.new_start)

    def old_len(self) -> int:
        if not self.parsed_content:
            return 0
        return sum(1 for c in self.parsed_content if isinstance(c, Removal))

    def new_len(self) -> int:
        if not self.parsed_content:
            return 0
        return sum(1 for c in self.parsed_content if isinstance(c, Addition))

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

        if self.has_content:
            changes = format_content_json(self.parsed_content)
        elif self.is_file_rename:
            changes = {
                "type": "Rename",
                "old_file_path": self.old_file_path,
                "new_file_path": self.new_file_path,
            }
        elif self.is_file_addition:
            changes = {
                "type": "FileAddition",
                "new_file_path": self.new_file_path,
            }
        elif self.is_file_deletion:
            changes = {
                "type": "FileDeletion",
                "old_file_path": self.old_file_path,
            }
        else:
            logger.warning(
                "A diff chunk with no content and no special purpouse was found!: {chunk}".format(
                    chunk=self
                )
            )

        return json.dumps(changes, indent=2)

    def split_into_atomic_chunks(
        self,
    ) -> List["DiffChunk"]:
        """
        A list of the most granular, yet still valid, DiffChunks.
        """
        # cannot split non-pure hunks
        if not self.has_content:
            return [self]

        has_additions = any(isinstance(c, Addition) for c in self.parsed_content)
        has_removals = any(isinstance(c, Removal) for c in self.parsed_content)

        # cannot split mixed chunks
        if has_additions and has_removals:
            return [self]

        # pure chunks so we can do whatever
        final_chunks = []
        for line in self.parsed_content:
            sub_chunk = self.from_parsed_content_slice(
                self.old_file_path, self.new_file_path, self.file_mode, [line]
            )
            final_chunks.append(sub_chunk)

        return final_chunks

    @classmethod
    def from_hunk(cls, hunk: HunkWrapper) -> "DiffChunk":
        """
        Construct a DiffChunk from a single, parsed HunkWrapper.
        This is the standard factory for this class.
        """
        parsed_content: List[Union[Addition, Removal]] = []
        current_old_line = hunk.old_start
        current_new_line = hunk.new_start

        for line in hunk.hunk_lines:
            if line.startswith("+"):
                parsed_content.append(
                    Addition(content=line[1:], line_number=current_new_line)
                )
                current_new_line += 1
            elif line.startswith("-"):
                parsed_content.append(
                    Removal(content=line[1:], line_number=current_old_line)
                )
                current_old_line += 1
            elif line.strip() == "\\ No newline at end of file":
                # will always be at the end of the diff (so put a large line number)
                parsed_content.append(
                    Addition(content=line.strip(), line_number=current_new_line)
                )

        return cls(
            new_file_path=hunk.new_file_path,
            old_file_path=hunk.old_file_path,
            file_mode=hunk.file_mode,
            parsed_content=parsed_content,
            old_start=hunk.old_start,
            new_start=hunk.new_start,
        )

    @classmethod
    def from_parsed_content_slice(
        cls,
        old_file_path: str,
        new_file_path: str,
        file_mode: str,
        parsed_slice: List[Union[Addition, Removal]],
    ) -> "DiffChunk":
        """
        Creates a DiffChunk from a slice of parsed Addition/Removal objects.
        This factory method correctly calculates the start lines and content.
        """
        if not parsed_slice:
            raise ValueError("parsed_slice cannot be empty")

        removals = [item for item in parsed_slice if isinstance(item, Removal)]
        additions = [item for item in parsed_slice if isinstance(item, Addition)]

        if removals and not additions:
            # Pure Deletion: The 'new_start' is anchored to the line *before* the removal.
            old_start = removals[0].line_number
            new_start = max(0, old_start - 1)
        elif additions and not removals:
            # Pure Addition: The 'old_start' is anchored to the line *before* the addition.
            new_start = additions[0].line_number
            old_start = max(0, new_start - 1)
        elif removals and additions:
            # Modification: Both start lines are taken directly from the first items.
            old_start = removals[0].line_number
            new_start = additions[0].line_number
        else:
            raise ValueError("Invalid input parsed_slice")

        return cls(
            old_file_path=old_file_path,
            new_file_path=new_file_path,
            file_mode=file_mode,
            parsed_content=parsed_slice,
            old_start=old_start,
            new_start=new_start,
        )
