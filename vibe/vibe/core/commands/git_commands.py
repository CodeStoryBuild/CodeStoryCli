import subprocess
from typing import List, Optional, Tuple, Union
from ..data.models import HunkWrapper
from ..data.s_diff_chunk import StandardDiffChunk
from ..data.r_diff_chunk import RenameDiffChunk
from ..data.diff_chunk import DiffChunk
from ..data.empty_file_chunk import EmptyFileAdditionChunk
from ..data.file_deletion_chunk import FileDeletionChunk
from ..git_interface.interface import GitInterface


# In GitCommands file, update or replace HunkWrapper
class GitCommands:
    def __init__(self, git: GitInterface):
        self.git = git

    # -------------------------------
    # Core methods
    # -------------------------------

    def get_working_diff_with_renames(
        self, target: Optional[str] = None, similarity: int = 50
    ) -> List[HunkWrapper]:
        """
        Generates a list of raw hunks, correctly parsing rename-and-modify diffs.
        This is the authoritative source of diff information.
        Uses binary mode to avoid encoding issues with Unicode characters in diffs.
        """
        path_args = [target] if target else []
        # Use binary mode to properly handle Unicode characters (€, £, etc.)
        diff_output_bytes = self.git.run_git_binary(
            ["diff", "HEAD", "--unified=0", f"-M{similarity}"] + path_args
        )
        # Decode with error handling for robustness
        diff_output = None
        if diff_output_bytes:
            diff_output = diff_output_bytes.decode("utf-8", errors="replace")
        return self._parse_hunks_with_renames(diff_output)

    def _parse_hunks_with_renames(
        self, diff_output: Optional[str]
    ) -> List[HunkWrapper]:
        """
        Parses a unified diff output that may contain rename blocks.
        Extracts metadata about file operations (additions, deletions, renames).
        """
        hunks: List[HunkWrapper] = []
        if not diff_output or diff_output is None:
            return hunks

        file_blocks = diff_output.split("\ndiff --git ")

        for block in file_blocks:
            if not block.strip():
                continue

            lines = block.splitlines()
            if not lines:
                continue

            # Parse file operation metadata
            file_metadata = self._parse_file_metadata(block, lines)
            if not file_metadata["canonical_path"]:
                continue

            # Parse hunks within the block
            hunk_start_indices = [
                i for i, line in enumerate(lines) if line.startswith("@@ ")
            ]

            # Handle files with no hunks (pure operations)
            if not hunk_start_indices:
                hunks.append(self._create_no_content_hunk(file_metadata))
            else:
                # Process each hunk in the file
                for i, start_idx in enumerate(hunk_start_indices):
                    end_idx = (
                        hunk_start_indices[i + 1]
                        if i + 1 < len(hunk_start_indices)
                        else len(lines)
                    )
                    hunk_header = lines[start_idx]
                    hunk_body_lines = lines[start_idx + 1 : end_idx]

                    old_start, old_len, new_start, new_len = self._parse_hunk_start(
                        hunk_header
                    )

                    hunks.append(
                        HunkWrapper(
                            new_file_path=file_metadata["canonical_path"],
                            hunk_lines=hunk_body_lines,
                            old_start=old_start,
                            new_start=new_start,
                            old_len=old_len,
                            new_len=new_len,
                            old_file_path=(
                                file_metadata["old_path"]
                                if file_metadata["is_rename"]
                                else None
                            ),
                            file_mode=file_metadata["file_mode"],
                            is_file_addition=file_metadata["is_file_addition"],
                            is_file_deletion=file_metadata["is_file_deletion"],
                        )
                    )
        return hunks

    def _parse_file_metadata(self, block: str, lines: List[str]) -> dict:
        """
        Extract file operation metadata from a diff block.
        Returns a dictionary with file paths, operation flags, and mode information.
        """
        old_path, new_path = None, None
        is_rename = "rename from " in block
        is_file_addition = "new file mode" in block
        is_file_deletion = "deleted file mode" in block
        file_mode = None

        # Extract file mode if present (e.g., "new file mode 100755")
        mode_line = next((l for l in lines if l.startswith("new file mode ")), None)
        if mode_line:
            file_mode = mode_line[14:].strip()  # Extract the mode number

        if is_rename:
            # Extract paths from rename lines
            rename_from_line = next(
                (l for l in lines if l.startswith("rename from ")), None
            )
            if rename_from_line:
                old_path = rename_from_line[12:]

            rename_to_line = next(
                (l for l in lines if l.startswith("rename to ")), None
            )
            if rename_to_line:
                new_path = rename_to_line[10:]
        else:
            # Extract paths from standard diff headers
            rem_line = next((l for l in lines if l.startswith("--- a/")), None)
            if rem_line:
                old_path = rem_line[6:]

            add_line = next((l for l in lines if l.startswith("+++ b/")), None)
            if add_line:
                new_path = add_line[6:]

        # Determine canonical path
        canonical_path = new_path if new_path and new_path != "/dev/null" else old_path

        # For files with no --- or +++ lines (like empty new files),
        # parse the path from the first line "a/path b/path"
        if not canonical_path and lines:
            first_line = lines[0]
            if " b/" in first_line:
                # Extract "b/path" from "a/path b/path"
                b_part = first_line.split(" b/")[1] if " b/" in first_line else None
                if b_part:
                    new_path = b_part
                    canonical_path = new_path

        return {
            "canonical_path": canonical_path,
            "old_path": old_path,
            "new_path": new_path,
            "is_rename": is_rename,
            "is_file_addition": is_file_addition,
            "is_file_deletion": is_file_deletion,
            "file_mode": file_mode,
        }

    def _create_no_content_hunk(self, file_metadata: dict) -> HunkWrapper:
        """
        Create a HunkWrapper for files with no content changes (pure operations).
        """
        if file_metadata["is_rename"]:
            # Pure rename (no content change)
            return HunkWrapper(
                new_file_path=file_metadata["canonical_path"],
                hunk_lines=[],
                old_start=0,
                new_start=0,
                old_len=0,
                new_len=0,
                old_file_path=file_metadata["old_path"],
                file_mode=file_metadata["file_mode"],
                is_file_addition=False,
                is_file_deletion=False,
            )
        elif file_metadata["is_file_addition"]:
            # Empty new file (no content)
            return HunkWrapper(
                new_file_path=file_metadata["canonical_path"],
                hunk_lines=[],
                old_start=0,
                new_start=0,
                old_len=0,
                new_len=0,
                old_file_path=None,
                file_mode=file_metadata["file_mode"],
                is_file_addition=True,
                is_file_deletion=False,
            )
        elif file_metadata["is_file_deletion"]:
            # File deletion (deleted file mode)
            return HunkWrapper(
                new_file_path=file_metadata["canonical_path"],
                hunk_lines=[],
                old_start=1,  # Mark as deletion with old_start > 0
                new_start=-1,  # Mark as deletion with new_start < 0
                old_len=0,
                new_len=0,
                old_file_path=file_metadata["canonical_path"],
                file_mode=file_metadata["file_mode"],
                is_file_addition=False,
                is_file_deletion=True,
            )
        else:
            # Fallback for unexpected cases
            return HunkWrapper(
                new_file_path=file_metadata["canonical_path"],
                hunk_lines=[],
                old_start=0,
                new_start=0,
                old_len=0,
                new_len=0,
                old_file_path=None,
                file_mode=file_metadata["file_mode"],
                is_file_addition=False,
                is_file_deletion=False,
            )

    def _parse_hunk_start(self, header_line: str) -> Tuple[int, int, int, int]:
        """
        Extract old_start, old_len, new_start, new_len from @@ -x,y +a,b @@ header
        Returns: (old_start, old_len, new_start, new_len)
        """
        import re

        match = re.search(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", header_line)
        if match:
            old_start = int(match.group(1))
            old_len = int(match.group(2)) if match.group(2) else 1
            new_start = int(match.group(3))
            new_len = int(match.group(4)) if match.group(4) else 1
            return old_start, old_len, new_start, new_len
        return 0, 0, 0, 0

    def reset(self) -> None:
        """Reset staged changes (keeping working directory intact)"""
        self.git.run_git_text(["reset"])

    def track_untracked(self, target: Optional[str] = None) -> None:
        """
        Make untracked files tracked without staging their content, using 'git add -N'.
        """
        if target:
            self.git.run_git_text(["add", "-N", target])
        else:
            # Track all untracked files
            untracked = self.git.run_git_text(
                ["ls-files", "--others", "--exclude-standard"]
            ).splitlines()
            if not untracked:
                return
            self.git.run_git_text(["add", "-N"] + untracked)

    def need_reset(self) -> bool:
        """Checks if there are staged changes that need to be reset"""
        # 'git diff --cached --quiet' exits with 1 if there are staged changes, 0 otherwise
        result = subprocess.run(
            ["git", "-C", self.git.repo_path, "diff", "--cached", "--quiet"],
            capture_output=True,
        )
        return result.returncode != 0

    def need_track_untracked(self, target: Optional[str] = None) -> bool:
        """Checks if there are any untracked files within a target that need to be tracked."""
        path_args = [target] if target else []
        untracked_files = self.git.run_git_text(
            ["ls-files", "--others", "--exclude-standard"] + path_args
        )
        return bool(untracked_files.strip())

    def get_processed_diff(self, target: Optional[str] = None) -> List[DiffChunk]:
        """
        Parses the git diff once and converts each hunk directly into an
        atomic DiffChunk object (StandardDiffChunk, RenameDiffChunk,
        EmptyFileAdditionChunk, or FileDeletionChunk).
        """
        # Parse ONCE to get a list of HunkWrapper objects.
        hunks = self.get_working_diff_with_renames(target)

        chunks: List[DiffChunk] = []
        for hunk in hunks:
            if hunk.is_rename:
                # Create a chunk for the rename-and-modify hunk
                chunks.append(RenameDiffChunk.from_hunk(hunk))
            elif hunk.is_file_addition and len(hunk.hunk_lines) == 0:
                # Empty new file (no content)
                chunks.append(
                    EmptyFileAdditionChunk(
                        _file_path=hunk.new_file_path,
                        file_mode=hunk.file_mode or "100644",
                    )
                )
            elif hunk.is_file_deletion and len(hunk.hunk_lines) == 0:
                # File deletion without content
                chunks.append(FileDeletionChunk(_file_path=hunk.new_file_path))
            else:
                # Create a chunk for a standard hunk (including file additions/deletions with content)
                chunks.append(StandardDiffChunk.from_hunk(hunk))

        return chunks

    def get_current_branch(self) -> str:
        """
        Returns the name of the currently checked out branch.
        """
        return self.git.run_git_text(["rev-parse", "--abbrev-ref", "HEAD"]).strip()

    def get_current_base_commit_hash(self) -> str:
        """
        Returns the commit hash of the current HEAD (base commit).
        """
        return self.git.run_git_text(["rev-parse", "HEAD"]).strip()
