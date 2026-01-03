# -----------------------------------------------------------------------------
# /*
#  * Copyright (C) 2025 CodeStory
#  *
#  * This program is free software; you can redistribute it and/or modify
#  * it under the terms of the GNU General Public License as published by
#  * the Free Software Foundation; Version 2.
#  *
#  * This program is distributed in the hope that it will be useful,
#  * but WITHOUT ANY WARRANTY; without even the implied warranty of
#  * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  * GNU General Public License for more details.
#  *
#  * You should have received a copy of the GNU General Public License
#  * along with this program; if not, you can contact us at support@codestory.build
#  */
# -----------------------------------------------------------------------------

from dataclasses import dataclass

from codestory.core.diff.data.atomic_chunk import AtomicDiffChunk
from codestory.core.diff.data.line_changes import Addition, Removal


@dataclass(frozen=True)
class StandardDiffChunk(AtomicDiffChunk):
    # the file mode from git diff (e.g., b'100644', b'100755')
    file_mode: bytes | None = None
    # whether the chunk should have a "\\ no newline at end of file" at end of the chunk (for chunks with no additions/removals)
    contains_newline_fallback: bool = False

    # the structured content of this chunk (list of Addition/Removal objects)
    parsed_content: list[Addition | Removal] | None = None

    @property
    def has_content(self) -> bool:
        return self.parsed_content is not None and len(self.parsed_content) > 0

    # starting line number in the old file
    old_start: int | None = None
    # new_start is not stored, rather calculated during diff generation to allow for dynamic line offsets

    @property
    def line_anchor(self) -> int:
        """Return the old file line anchor for sorting chunks."""
        return self.old_start or 0

    def old_len(self) -> int:
        if self.parsed_content is None:
            return 0
        return sum(1 for c in self.parsed_content if isinstance(c, Removal))

    def new_len(self) -> int:
        if self.parsed_content is None:
            return 0
        return sum(1 for c in self.parsed_content if isinstance(c, Addition))

    def get_abs_new_line_start(self) -> int | None:
        """Get the absolute new file line start (for semantic grouping ONLY!).

        This finds the abs_new_line value from the first Addition in the
        chunk. Returns None if there are no additions.
        """
        if not self.parsed_content:
            return None
        for item in self.parsed_content:
            if isinstance(item, Addition):
                return item.abs_new_line
        return None

    def get_abs_new_line_end(self) -> int | None:
        """Get the absolute new file line end (for semantic grouping ONLY!).

        This finds the abs_new_line value from the last Addition in the
        chunk. Returns None if there are no additions.
        """
        if not self.parsed_content:
            return None
        for item in reversed(self.parsed_content):
            if isinstance(item, Addition):
                return item.abs_new_line
        return None

    def get_min_abs_line(self) -> int:
        """Get the minimum absolute line number for sorting chunks.

        This returns the minimum of all abs_new_line values in the
        chunk. Used for determining relative positioning of chunks.
        Falls back to old_start if no abs_new_line values exist.
        """
        if not self.parsed_content:
            return self.old_start or 0

        abs_lines = [item.abs_new_line for item in self.parsed_content]
        return min(abs_lines) if abs_lines else (self.old_start or 0)

    def get_old_line_range(self) -> tuple[int, int]:
        """Get the range of old file lines this chunk covers.

        Returns (start, end) inclusive range in old file coordinates.
        """
        if not self.old_start:
            return (0, 0)
        return (self.old_start, self.old_start + self.old_len() - 1)

    def get_abs_new_line_range(self) -> tuple[int | None, int | None]:
        """Get the range of absolute new file lines this chunk covers.

        Returns (start, end) inclusive range in absolute new file
        coordinates. Returns (None, None) if no additions exist.
        """
        start = self.get_abs_new_line_start()
        end = self.get_abs_new_line_end()
        if start is None or end is None:
            return (None, None)
        return (start, end)

    def get_sort_key(self) -> tuple[int, int]:
        """Get a sort key for maintaining correct chunk order.

        Returns (old_start, min_abs_new_line) tuple. This ensures chunks
        are sorted by old file position first, then by new file position
        for chunks at the same old position.
        """
        return (self.old_start or 0, self.get_min_abs_line())

    def is_disjoint_from(self, other: "StandardDiffChunk") -> bool:
        """Check if this chunk is disjoint from another chunk (in old file coordinates).

        Two chunks are disjoint if their old file ranges don't overlap.
        This is the key property that allows chunks to be applied in any
        order.

        For pure insertions at the same old_start, we use abs_new_line
        to determine if they're at different insertion points.
        """
        if not other or self.canonical_path() != other.canonical_path():
            # Different files are always disjoint
            return True

        self_start = self.old_start or 0
        self_end = self_start + self.old_len()
        other_start = other.old_start or 0
        other_end = other_start + other.old_len()

        # Special case: Two pure insertions at the same old_start
        # They are technically covering the same "gap" in the old file, but we treat them as
        # disjoint chunks because they represent distinct added content lists.
        # The order is determined by get_sort_key() (abs_new_line).
        if self.old_len() == 0 and other.old_len() == 0 and self_start == other_start:
            return True

        # Disjoint if one ends before the other starts
        return self_end <= other_start or other_end <= self_start

    def pure_addition(self) -> bool:
        return self.old_len() == 0 and self.has_content

    def pure_deletion(self) -> bool:
        return self.new_len() == 0 and self.has_content

    @staticmethod
    def _sanitize_patch_content(content: bytes) -> bytes:
        """Sanitize text for use in a Git patch."""
        return content

    @classmethod
    def from_parsed_content_slice(
        cls,
        base_hash: str,
        new_hash: str,
        old_file_path: bytes | None,
        new_file_path: bytes | None,
        file_mode: bytes | None,
        contains_newline_fallback: bool,
        parsed_slice: list[Addition | Removal],
    ) -> "StandardDiffChunk":
        """Create a DiffChunk from a slice of parsed content."""
        if not parsed_slice:
            raise ValueError("parsed_slice cannot be empty")

        removals = [item for item in parsed_slice if isinstance(item, Removal)]
        additions = [item for item in parsed_slice if isinstance(item, Addition)]

        # Calculate old_start based on the first change in old file coordinates
        if removals:
            # If there are removals, old_start is the first removal's old_line
            old_start = removals[0].old_line
        elif additions:
            # If only additions, old_start is where we're inserting in the old file
            # For pure additions, old_line represents the line AFTER which we insert
            # So old_start should be old_line (or 0 for new files)
            old_start = 0 if old_file_path is None else additions[0].old_line
        else:
            raise ValueError("Invalid input parsed_slice")

        return cls(
            base_hash=base_hash,
            new_hash=new_hash,
            old_file_path=old_file_path,
            new_file_path=new_file_path,
            file_mode=file_mode,
            contains_newline_fallback=contains_newline_fallback,
            parsed_content=parsed_slice,
            old_start=old_start,
        )
