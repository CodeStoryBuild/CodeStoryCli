from vibe.core.data.diff_chunk import DiffChunk
from vibe.core.data.models import Addition, Removal, HunkWrapper, ChunkApplicationData
from dataclasses import dataclass
from typing import List, Optional, Union
import json

from .utils import format_content_json


@dataclass(frozen=True)
class StandardDiffChunk(DiffChunk):
    """
    Represents a single diff chunk or sub-hunk.

    Responsibilities:
    - Must contain enough information to reconstruct a patch for Git
    - Preserves file path, line numbers, and content
    - Can be serialized into a unified diff format
    - GUARANTEES that parsed_content represents a contiguous block of changes

    Attributes:
        _file_path: Path of the file this chunk belongs to
        start_line: Start line number in the original file
        end_line: End line number in the original file
        parsed_content: A structured, AI-legible list of Addition and Removal objects (MUST be contiguous)
        old_start: Optional start line in original version (for patch)
        new_start: Optional start line in new version
        file_mode: Optional file mode from git diff (e.g., '100644', '100755')
        is_file_addition: True if this chunk is part of a new file being added
        is_file_deletion: True if this chunk is part of a file being deleted
    """

    _file_path: str
    parsed_content: List[Union[Addition, Removal]]
    old_start: int
    new_start: int
    file_mode: Optional[str] = None
    is_file_addition: bool = False
    is_file_deletion: bool = False

    def __post_init__(self):
        """Validate that this chunk represents a contiguous block of changes."""
        self._validate_contiguity()

    def _validate_contiguity(self):
        """
        Validates that parsed_content represents a contiguous block of changes.

        Rules for git patch contiguity:
        1. All removals must be on consecutive line numbers starting from old_start
        2. All additions must be on consecutive line numbers starting from new_start
        3. old_start and new_start can be different (this is normal for git patches)

        Raises:
            ValueError: If the chunk is not contiguous within its removal/addition blocks
        """
        if not self.parsed_content:
            return

        # Separate removals and additions
        removals = [item for item in self.parsed_content if isinstance(item, Removal)]
        additions = [item for item in self.parsed_content if isinstance(item, Addition)]

        # Check that removals are contiguous starting from old_start
        if removals:
            removal_lines = sorted([r.line_number for r in removals])
            expected_line = self.old_start
            for actual_line in removal_lines:
                if actual_line != expected_line:
                    raise ValueError(
                        f"Non-contiguous removals: expected line {expected_line}, got {actual_line}"
                    )
                expected_line += 1

        # Check that additions are contiguous starting from new_start
        if additions:
            addition_lines = sorted([a.line_number for a in additions])
            expected_line = self.new_start
            for actual_line in addition_lines:
                if actual_line != expected_line:
                    raise ValueError(
                        f"Non-contiguous additions: expected line {expected_line}, got {actual_line}"
                    )
                expected_line += 1

    def get_min_line(self):
        return min(self.parsed_content, key=lambda c: c.line_number).line_number

    def get_max_line(self):
        return max(self.parsed_content, key=lambda c: c.line_number).line_number

    def get_total_lines(self):
        return self.get_max_line() - self.get_min_line() + 1

    def format_json(self) -> str:
        output_data = {
            "file_path": self._file_path,
            "new_start": self.new_start,
            "old_start": self.old_start,
            "changes": format_content_json(self.parsed_content),
        }
        return json.dumps(output_data)

    def get_chunk_application_data(self) -> List[ChunkApplicationData]:
        """
        Converts this StandardDiffChunk into ChunkApplicationData format for the synthesizer.

        This method encapsulates the logic for converting parsed_content (Addition/Removal objects)
        into the format needed to apply the changes to files.

        Returns:
            A list containing a single ChunkApplicationData object representing this chunk's changes.
        """
        removals = [item for item in self.parsed_content if isinstance(item, Removal)]
        additions = [item for item in self.parsed_content if isinstance(item, Addition)]

        # If a chunk has both removals and additions, it's a "replace" operation.
        # The anchor point for applying the change is always the start of the removal.
        if removals and additions:
            return [
                ChunkApplicationData(
                    start_line=self.old_start,
                    line_count=len(removals),
                    add_content=[item.content for item in additions],
                )
            ]
        # If it only has removals, it's a pure deletion.
        elif removals:
            return [
                ChunkApplicationData(
                    start_line=self.old_start,
                    line_count=len(removals),
                    add_content=[],
                )
            ]
        # If it only has additions, it's a pure addition.
        elif additions:
            return [
                ChunkApplicationData(
                    start_line=self.old_start + 1,
                    line_count=0,
                    add_content=[item.content for item in additions],
                )
            ]
        else:
            # Empty chunk - shouldn't happen but handle gracefully
            return []

    def file_path(self):
        return self._file_path

    @classmethod
    def from_hunk(cls, hunk: "HunkWrapper") -> "StandardDiffChunk":
        """
        Construct a StandardDiffChunk from a single, parsed HunkWrapper.
        This is the standard factory for this class.
        """
        if hunk.is_rename:
            raise ValueError("StandardDiffChunk cannot be created from a rename hunk.")

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

        return cls(
            _file_path=hunk.new_file_path,
            parsed_content=parsed_content,
            old_start=hunk.old_start,
            new_start=hunk.new_start,
            file_mode=hunk.file_mode,
            is_file_addition=hunk.is_file_addition,
            is_file_deletion=hunk.is_file_deletion,
        )

    @classmethod
    def from_parsed_content_slice(
        cls,
        file_path: str,
        parsed_slice: List[Union[Addition, Removal]],
        file_mode,
        is_file_addition,
        is_file_deletion,
    ) -> Optional["StandardDiffChunk"]:
        """
        Creates a StandardDiffChunk from a slice of parsed Addition/Removal objects.
        This factory method correctly calculates the start lines and content.
        """
        if not parsed_slice:
            return None

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

        # Directly instantiate the class, allowing __post_init__ to run its validation.
        return cls(
            _file_path=file_path,
            parsed_content=parsed_slice,
            old_start=old_start,
            new_start=new_start,
            file_mode=file_mode,
            is_file_addition=is_file_addition,
            is_file_deletion=is_file_deletion,
        )
