from dataclasses import dataclass
import json
import re
from typing import List

from .diff_chunk import DiffChunk
from ..data.models import ChunkApplicationData, HunkWrapper


@dataclass(frozen=True)
class RenameDiffChunk(DiffChunk):
    old_file_path: str
    new_file_path: str
    patch_content: str  # Store the raw patch (hunk headers + lines)
    application_data: List[ChunkApplicationData]  # Pre-parsed data for the synthesizer

    def file_path(self) -> str:
        """For grouping purposes, a rename is associated with its new path."""
        return self.new_file_path

    def format_json(self) -> str:
        data = {
            "type": "Rename",
            "old_file_path": self.old_file_path,
            "new_file_path": self.new_file_path,
            "patch_content": self.patch_content,
        }
        return json.dumps(data, indent=2)

    def get_chunk_application_data(self) -> List[ChunkApplicationData]:
        """
        Returns the pre-parsed application data for this rename chunk.

        The application data was already computed during initialization from the patch content.

        Returns:
            The list of ChunkApplicationData objects for applying this rename's changes.
        """
        return self.application_data

    @classmethod
    def from_raw_patch(
        cls, old_file_path: str, new_file_path: str, patch_content: str
    ) -> "RenameDiffChunk":
        """Creates a chunk by parsing a raw patch string."""
        app_data = cls._parse_patch(patch_content)
        return cls(old_file_path, new_file_path, patch_content, app_data)

    @classmethod
    def from_hunk(cls, hunk: "HunkWrapper") -> "RenameDiffChunk":
        """Constructs a RenameDiffChunk directly from a parsed HunkWrapper."""
        if not hunk.is_rename:
            raise ValueError("Cannot create a RenameDiffChunk from a non-rename hunk.")

        # 1. Reconstruct the patch content string for storage/display
        hunk_header = (
            f"@@ -{hunk.old_start},{hunk.old_len} +{hunk.new_start},{hunk.new_len} @@"
        )
        patch_content = "\n".join([hunk_header] + hunk.hunk_lines)

        # 2. Calculate application_data DIRECTLY from hunk properties
        add_content = [line[1:] for line in hunk.hunk_lines if not line.startswith("-")]
        removals_count = sum(1 for line in hunk.hunk_lines if line.startswith("-"))

        start_line = hunk.old_start
        # Handle pure additions where old_len is 0
        if hunk.old_len == 0:
            start_line += 1
            removals_count = 0  # Should already be 0, but good to be explicit

        app_data = [
            ChunkApplicationData(
                start_line=start_line,
                line_count=removals_count,
                add_content=add_content,
            )
        ]

        # 3. Call the main constructor with pre-calculated data
        return cls(
            old_file_path=hunk.old_file_path,
            new_file_path=hunk.new_file_path,
            patch_content=patch_content,
            application_data=app_data,
        )

    @staticmethod
    def _parse_patch(patch_content: str) -> List[ChunkApplicationData]:
        """Parses a patch string into a list of application data for the synthesizer."""
        application_data = []

        # This logic is designed for multiple hunks, but works perfectly fine for one.
        hunks = re.split(r"\n(?=@@)", patch_content.strip())

        for hunk in hunks:
            if not hunk.strip() or not hunk.startswith("@@"):
                continue

            # Match the hunk header to get line numbers
            header_match = re.search(
                r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", hunk
            )
            if not header_match:
                continue

            old_start = int(header_match.group(1))

            # Get the body lines of the hunk
            lines = hunk.splitlines()
            body_lines = lines[1:] if len(lines) > 1 else []

            # Calculate the content to be added and the number of lines to be removed
            add_content = [line[1:] for line in body_lines if not line.startswith("-")]
            removals_count = sum(1 for line in body_lines if line.startswith("-"))

            # Handle edge case for pure additions where diff shows `@@ -N,0 ... @@`
            # The change should be applied *after* line N.
            old_len_str = header_match.group(2)
            if old_len_str == "0":
                old_start += 1
                # In this case, there can be no removals.
                removals_count = 0

            application_data.append(
                ChunkApplicationData(
                    start_line=old_start,
                    line_count=removals_count,
                    add_content=add_content,
                )
            )
        return application_data
