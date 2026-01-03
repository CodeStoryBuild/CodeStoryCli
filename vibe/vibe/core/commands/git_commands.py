import subprocess
from typing import List, Optional, Tuple
from ..data.models import HunkWrapper
from ..data.s_diff_chunk import StandardDiffChunk
from ..data.r_diff_chunk import RenameDiffChunk
from ..data.diff_chunk import DiffChunk
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
        """
        path_args = [target] if target else []
        diff_output = self.git.run_git_text(
            ["diff", "HEAD", "--unified=0", f"-M{similarity}"] + path_args
        )
        return self._parse_hunks_with_renames(diff_output)

    def _parse_hunks_with_renames(self, diff_output: str) -> List[HunkWrapper]:
        """
        Parses a unified diff output that may contain rename blocks.
        This version is slightly improved to capture the hunk header.
        """
        hunks: List[HunkWrapper] = []
        file_blocks = diff_output.split("\ndiff --git ")

        for block in file_blocks:
            if not block.strip():
                continue

            lines = block.splitlines()
            if not lines:
                continue

            # --- Parse File Header ---
            old_path, new_path = None, None
            is_rename = "rename from " in block

            if is_rename:
                rename_from_line = next(
                    (l for l in lines if l.startswith("rename from ")), None
                )
                old_path = rename_from_line[12:]
                rename_to_line = next(
                    (l for l in lines if l.startswith("rename to ")), None
                )
                new_path = rename_to_line[10:]
            else:
                rem_line = next((l for l in lines if l.startswith("--- a/")), None)
                if rem_line:
                    old_path = rem_line[6:]

                add_line = next((l for l in lines if l.startswith("+++ b/")), None)
                if add_line:
                    new_path = add_line[6:]

            canonical_path = (
                new_path if new_path and new_path != "/dev/null" else old_path
            )
            if not canonical_path:
                continue

            # --- Parse Hunks within the Block ---
            hunk_start_indices = [
                i for i, line in enumerate(lines) if line.startswith("@@ ")
            ]

            # Handle pure renames (no hunks)
            if not hunk_start_indices and is_rename:
                hunks.append(
                    HunkWrapper(
                        new_file_path=canonical_path,
                        hunk_lines=[],
                        old_start=0,
                        new_start=0,
                        old_file_path=old_path,
                    )
                )

            for i, start_idx in enumerate(hunk_start_indices):
                end_idx = (
                    hunk_start_indices[i + 1]
                    if i + 1 < len(hunk_start_indices)
                    else len(lines)
                )
                hunk_header = lines[start_idx]
                hunk_body_lines = lines[start_idx + 1 : end_idx]

                old_start, new_start = self._parse_hunk_start(hunk_header)

                hunks.append(
                    HunkWrapper(
                        new_file_path=canonical_path,
                        hunk_lines=hunk_body_lines,
                        old_start=old_start,
                        new_start=new_start,
                        old_file_path=old_path if is_rename else None,
                    )
                )
        return hunks

    def _parse_hunk_start(self, header_line: str) -> Tuple[int, int]:
        """
        Extract old_start and new_start from @@ -x,y +a,b @@ header
        """
        import re

        match = re.search(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", header_line)
        if match:
            return int(match.group(1)), int(match.group(2))
        return 0, 0

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
        atomic DiffChunk object (StandardDiffChunk or RenameDiffChunk).
        """
        # Parse ONCE to get a list of HunkWrapper objects.
        hunks = self.get_working_diff_with_renames(target)

        chunks: List[DiffChunk] = []
        for hunk in hunks:
            if hunk.is_rename:
                # Create a chunk for the rename-and-modify hunk
                chunks.append(RenameDiffChunk.from_hunk(hunk))
            else:
                # Create a chunk for a standard hunk
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
