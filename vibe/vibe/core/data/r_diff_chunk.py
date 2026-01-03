from dataclasses import dataclass
import json
import re
from typing import List

from .diff_chunk import DiffChunk
from ..data.models import ChunkApplicationData, HunkWrapper


@dataclass(frozen=True, init=False)
class RenameDiffChunk(DiffChunk):
    old_file_path: str
    new_file_path: str
    patch_content: str  # Store the raw patch (hunk headers + lines)
    application_data: List[ChunkApplicationData]  # Pre-parsed data for the synthesizer

    def __init__(self, old_file_path: str, new_file_path: str, patch_content: str):
        # Use object.__setattr__ because the class is frozen
        object.__setattr__(self, "old_file_path", old_file_path)
        object.__setattr__(self, "new_file_path", new_file_path)
        object.__setattr__(self, "patch_content", patch_content)
        object.__setattr__(self, "application_data", self._parse_patch(patch_content))

    @classmethod
    def from_hunk(cls, hunk: "HunkWrapper") -> "RenameDiffChunk":
        """
        Construct a RenameDiffChunk directly from a single parsed HunkWrapper.
        This method reconstructs a minimal patch string to feed the main constructor.
        """
        if not hunk.is_rename:
            raise ValueError("Cannot create a RenameDiffChunk from a non-rename hunk.")

        # Reconstruct the patch content string for this single hunk
        # The header must be regenerated to be passed to __init__
        hunk_header = f"@@ -{hunk.old_start},0 +{hunk.new_start},0 @@"  # A simplified, valid header

        # Combine the header and the body lines to form the patch content
        patch_lines = [hunk_header] + hunk.hunk_lines
        patch_content = "\n".join(patch_lines)

        # Call the main constructor with the required arguments
        return cls(
            old_file_path=hunk.old_file_path,
            new_file_path=hunk.new_file_path,
            patch_content=patch_content,
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

    # --- Properties to conform to interfaces ---

    @property
    def file_path(self) -> str:
        """For grouping purposes, a rename is associated with its new path."""
        return self.new_file_path

    @property
    def content(self) -> str:
        """Provides a consistent content interface."""
        return self.patch_content

    def format_json(self) -> str:
        data = {
            "type": "Rename",
            "old_file_path": self.old_file_path,
            "new_file_path": self.new_file_path,
            "patch_content": self.patch_content,
        }
        return json.dumps(data, indent=2)
