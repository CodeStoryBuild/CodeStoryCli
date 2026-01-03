from itertools import groupby
from typing import List, Optional, Tuple, Union
import re

from ..data.hunk_wrapper import HunkWrapper
from ..data.diff_chunk import DiffChunk
from ..data.composite_diff_chunk import CompositeDiffChunk
from ..git_interface.interface import GitInterface


# In GitCommands file, update or replace HunkWrapper
class GitCommands:

    def __init__(self, git: GitInterface):
        self.git = git

    # Precompile diff regexes for performance
    _MODE_RE = re.compile(
        r"^(?:new file mode|deleted file mode|old mode|new mode) (\d{6})$"
    )
    _INDEX_RE = re.compile(r"^index [0-9a-f]{7,}\.\.[0-9a-f]{7,}(?: (\d{6}))?$")
    _RENAME_FROM_RE = re.compile(r"^rename from (.+)$")
    _RENAME_TO_RE = re.compile(r"^rename to (.+)$")
    _OLD_PATH_RE = re.compile(r"^--- (?:(?:a/)?(.+)|/dev/null)$")
    _NEW_PATH_RE = re.compile(r"^\+\+\+ (?:(?:b/)?(.+)|/dev/null)$")
    _A_B_PATHS_RE = re.compile(r".*a/(.+?) b/(.+)")

    def get_working_diff_with_renames(
        self,
        base_hash: str,
        new_hash: str,
        target: Optional[str] = None,
        similarity: int = 50,
    ) -> List[HunkWrapper]:
        """
        Generates a list of raw hunks, correctly parsing rename-and-modify diffs.
        This is the authoritative source of diff information.
        Uses binary mode to avoid encoding issues with Unicode characters in diffs.
        """
        path_args = ["--"] + ([target] if target else [])
        diff_output_bytes = self.git.run_git_binary(
            ["diff", base_hash, new_hash, "--unified=0", f"-M{similarity}"] + path_args
        )
        # Decode with error handling for robustness
        diff_output = None
        if diff_output_bytes:
            diff_output = diff_output_bytes.decode("utf-8", errors="replace")
        return self._parse_hunks_with_renames(diff_output)

    def get_file_diff_with_renames(
        self, fileA: str, fileB: str, similarity: int = 50
    ) -> List[HunkWrapper]:
        """
        Generates a list of raw hunks, correctly parsing rename-and-modify diffs.
        This is the authoritative source of diff information.
        Uses binary mode to avoid encoding issues with Unicode characters in diffs.
        """
        # Use binary mode to properly handle Unicode characters (€, £, etc.)
        diff_output_bytes = self.git.run_git_binary(
            ["diff", "--no-index", "--unified=0", f"-M{similarity}", "--", fileA, fileB]
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
            old_path, new_path, file_mode = self._parse_file_metadata(lines)

            if old_path is None and new_path is None:
                raise ValueError(
                    "Both old and new file paths are None! Invalid /dev/null parsing!"
                )
            elif not old_path and not new_path:
                raise ValueError("Could not parse file paths from diff block!")
        
            # Parse hunks within the block
            hunk_start_indices = [
                i for i, line in enumerate(lines) if line.startswith("@@ ")
            ]

            # Handle files with no hunks (pure operations)
            if not hunk_start_indices:
                hunks.append(
                    HunkWrapper.create_empty_content(
                        new_file_path=new_path,
                        old_file_path=old_path,
                        file_mode=file_mode,
                    )
                )
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
                            new_file_path=new_path,
                            old_file_path=old_path,
                            file_mode=file_mode,
                            hunk_lines=hunk_body_lines,
                            old_start=old_start,
                            new_start=new_start,
                            old_len=old_len,
                            new_len=new_len,
                        )
                    )
        return hunks

    def _parse_file_metadata(self, lines: List[str]) -> tuple:
        """
        Extracts file operation metadata from a diff block by unifying the logic
        around the '---' and '+++' file path lines.

        Returns a dictionary with file paths, operation flags, and mode information.
        """
        old_path, new_path = "", ""
        file_mode = None

        # 1. First pass: Extract primary data (paths and mode)
        for line in lines:
            # Check for file mode (new, deleted, old, new)
            mode_match = self._MODE_RE.match(line)
            if mode_match:
                # We only need one mode; Git diffs can show old and new.
                # The one on the 'new file mode' or 'deleted file mode' line is most relevant.
                if file_mode is None or "file mode" in line:
                    file_mode = mode_match.group(1)
                continue

            old_path_match = self._OLD_PATH_RE.match(line)
            if old_path_match:
                if line.strip() == "--- /dev/null":
                    old_path = None
                else:
                    old_path = old_path_match.group(1)
                continue

            new_path_match = self._NEW_PATH_RE.match(line)
            if new_path_match:
                if line.strip() == "+++ /dev/null":
                    new_path = None
                else:
                    new_path = new_path_match.group(1)
                continue

        # fallback for cases like:
        # a/src/api/__init__.py b/src/api/__init__.py
        # new file mode 100644
        # index 0000000..e69de29
        # no --- or +++ lines
        if not old_path and not new_path:
            # Use regex to robustly extract a/ and b/ paths from the first line
            path_a, path_b = None, None
            for line in lines:
                m = self._A_B_PATHS_RE.match(lines[0])
                if not m:
                    return (None, None, file_mode)  # Unrecognized format
                path_a = m.group(1)
                path_b = m.group(2)

            # Use other metadata clues from the block to determine the operation
            block_text = "\n".join(lines)
            if "new file mode" in block_text:
                # This is an empty file addition.
                return (None, path_b, file_mode)
            elif "deleted file mode" in block_text:
                # This is an empty file deletion (less common, but possible).
                return (path_a, None, file_mode)
            elif "rename from" in block_text:
                # This is a pure rename with no content change.
                return (path_a, path_b, file_mode)
            else:
                # Could be a pure mode change.
                return (path_a, path_b, file_mode)

        return (old_path, new_path, file_mode)

    def _create_no_content_hunk(self, file_metadata: dict) -> HunkWrapper:
        """
        Create a HunkWrapper for files with no content changes (pure operations).
        """
        if file_metadata["is_rename"]:
            # Pure rename (no content change)
            return HunkWrapper.create_empty_rename(
                new_file_path=file_metadata["canonical_path"],
                old_file_path=file_metadata["old_path"],
                file_mode=file_metadata["file_mode"],
            )
        elif file_metadata["is_file_addition"]:
            # Empty new file (no content)
            return HunkWrapper.create_empty_addition(
                new_file_path=file_metadata["canonical_path"],
                file_mode=file_metadata["file_mode"],
            )
        elif file_metadata["is_file_deletion"]:
            # File deletion (deleted file mode)
            return HunkWrapper.create_empty_deletion(
                old_file_path=file_metadata["canonical_path"],
                file_mode=file_metadata["file_mode"],
            )

        else:
            raise ValueError("Cannot create no-content hunk for unknown operation.")

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
        try:
            self.git.run_git_text(["diff", "--cached", "--quiet"])
            return False  # No staged changes (exit code 0)
        except Exception:
            return True  # Staged changes exist (exit code 1)

    def need_track_untracked(self, target: Optional[str] = None) -> bool:
        """Checks if there are any untracked files within a target that need to be tracked."""
        path_args = [target] if target else []
        untracked_files = self.git.run_git_text(
            ["ls-files", "--others", "--exclude-standard"] + path_args
        )
        return bool(untracked_files.strip())

    def is_git_repo(self) -> bool:
        """Return True if current cwd is inside a git work tree, else False."""
        result = self.git.run_git_text(["rev-parse", "--is-inside-work-tree"])
        # When not a repo, run_git_text returns None; treat as False
        return bool(result and result.strip() == "true")

    def get_processed_working_diff(
        self, base_hash: str, new_hash: str, target: Optional[str] = None
    ) -> List[DiffChunk]:
        """
        Parses the git diff once and converts each hunk directly into an
        atomic DiffChunk object (DiffChunk).
        """
        # Parse ONCE to get a list of HunkWrapper objects.
        hunks = self.get_working_diff_with_renames(base_hash, new_hash, target)
        return self.parse_and_merge_hunks(hunks)

    def parse_and_merge_hunks(
        self, hunks: List[HunkWrapper]
    ) -> List[Union[DiffChunk, "CompositeDiffChunk"]]:
        chunks: List[DiffChunk] = []
        for hunk in hunks:
            chunks.append(DiffChunk.from_hunk(hunk))

        # Merge overlapping or touching chunks into CompositeDiffChunks
        merged = self.merge_overlapping_chunks(chunks)
        return merged

    def merge_overlapping_chunks(
        self, chunks: List[DiffChunk]
    ) -> List[Union[DiffChunk, "CompositeDiffChunk"]]:
        """
        Merge DiffChunks that are not disjoint (i.e., overlapping or touching)
        into CompositeDiffChunks, grouped per canonical path (file).

        A merge occurs if two chunks within the same file overlap or touch
        in either their old or new line ranges.

        Returns:
            A list of DiffChunk and CompositeDiffChunk objects, each representing
            a disjoint edit region.
        """
        if not chunks:
            return []

        # Sort once globally by canonical path, then by old/new start lines
        chunks_sorted = sorted(
            chunks,
            key=lambda c: (
                c.canonical_path(),
                c.old_start if c.old_start is not None else -1,
                c.new_start if c.new_start is not None else -1,
            ),
        )

        merged_results: List[Union[DiffChunk, "CompositeDiffChunk"]] = []

        # Helper for overlap/touch logic
        def overlaps_or_touches(a: DiffChunk, b: DiffChunk) -> bool:
            a_old_end = (a.old_start or 0) + a.old_len()
            b_old_start = b.old_start or 0

            a_new_end = (a.new_start or 0) + a.new_len()
            b_new_start = b.new_start or 0

            return (a_old_end >= b_old_start) or (a_new_end >= b_new_start)

        # Group by canonical path (so merges only happen within same file)
        for path, group in groupby(chunks_sorted, key=lambda c: c.canonical_path()):
            file_chunks = list(group)
            if not file_chunks:
                continue

            current_group: List[DiffChunk] = [file_chunks[0]]

            for h in file_chunks[1:]:
                last = current_group[-1]
                if overlaps_or_touches(last, h):
                    current_group.append(h)
                else:
                    # finalize group
                    if len(current_group) == 1:
                        merged_results.append(current_group[0])
                    else:
                        merged_results.append(CompositeDiffChunk(current_group.copy()))
                    current_group = [h]

            # finalize last group (if present)
            if current_group:
                if len(current_group) == 1:
                    merged_results.append(current_group[0])
                else:
                    merged_results.append(CompositeDiffChunk(current_group))

        return merged_results

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
