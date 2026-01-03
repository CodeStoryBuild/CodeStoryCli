from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import re
import tempfile
from typing import Dict, List, Optional, Tuple
from ..data.models import CommitGroup, CommitResult
from ..data.s_diff_chunk import StandardDiffChunk
from ..data.r_diff_chunk import RenameDiffChunk
from ..data.diff_chunk import DiffChunk
from ..git_interface.interface import GitInterface

# In GitCommands file, update or replace HunkWrapper

@dataclass
class HunkWrapper:
    # new_file_path is the primary path for modifications or additions.
    new_file_path: str
    hunk_lines: List[str]
    old_start: int
    new_start: int
    # old_file_path is None unless this hunk is part of a rename.
    old_file_path: Optional[str] = None

    @property
    def is_rename(self) -> bool:
        return self.old_file_path is not None

    @property
    def file_path(self) -> str:
        # For backward compatibility or simple logic, provide a single file_path.
        return self.new_file_path

class GitCommands:
    def __init__(self, git: GitInterface):
        self.git = git

    # -------------------------------
    # Core methods
    # -------------------------------

    def get_working_diff_with_renames(self, target: Optional[str] = None, similarity: int = 50) -> List[HunkWrapper]:
        """
        Generates a list of raw hunks, correctly parsing rename-and-modify diffs.
        This is the authoritative source of diff information.
        """
        path_args = [target] if target else []
        # Use -M to detect renames IN the diff output itself
        diff_output = self.git.run_git_text(["diff", "HEAD", "--unified=0", f"-M{similarity}"] + path_args)
        return self._parse_hunks_with_renames(diff_output)

    def _parse_hunks_with_renames(self, diff_output: str) -> List[HunkWrapper]:
        """
        Parses a unified diff output that may contain rename blocks.
        A rename block looks like:
        diff --git a/old_path b/new_path
        similarity index XX%
        rename from old_path
        rename to new_path
        --- a/old_path
        +++ b/new_path
        @@ ... @@
        """
        hunks: List[HunkWrapper] = []
        # Split by the diff header, which is consistent
        file_blocks = diff_output.split("\ndiff --git ")

        for block in file_blocks:
            if not block.strip():
                continue
            
            lines = block.splitlines()

            # Default paths
            old_path, new_path = None, None
            is_rename = False

            # Parse header lines for file paths and rename status
            rename_from_line = next((l for l in lines if l.startswith("rename from ")), None)
            if rename_from_line:
                is_rename = True
                old_path = rename_from_line[12:]
                rename_to_line = next((l for l in lines if l.startswith("rename to ")), None)
                new_path = rename_to_line[10:] if rename_to_line else None
            else:
                # Standard diff path parsing
                rem_line = next((l for l in lines if l.startswith("--- a/")), None)
                if rem_line: old_path = rem_line[6:]
                
                add_line = next((l for l in lines if l.startswith("+++ b/")), None)
                if add_line: new_path = add_line[6:]
            
            # Determine the canonical path for modifications
            canonical_path = new_path if new_path and new_path != "/dev/null" else old_path
            if not canonical_path:
                continue
            
            # Find hunks within this block
            hunk_start_indices = [i for i, line in enumerate(lines) if line.startswith("@@ ")]
            for i, start_idx in enumerate(hunk_start_indices):
                end_idx = hunk_start_indices[i+1] if i + 1 < len(hunk_start_indices) else len(lines)
                hunk_lines = lines[start_idx+1:end_idx]
                
                old_start, new_start = self._parse_hunk_start(lines[start_idx])

                hunks.append(HunkWrapper(
                    new_file_path=canonical_path,
                    hunk_lines=hunk_lines,
                    old_start=old_start,
                    new_start=new_start,
                    old_file_path=old_path if is_rename else None
                ))
                
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
            untracked = self.git.run_git_text(["ls-files", "--others", "--exclude-standard"]).splitlines()
            if not untracked:
                return
            self.git.run_git_text(["add", "-N"] + untracked)

    def need_reset(self) -> bool:
        """Checks if there are staged changes that need to be reset"""
        # 'git diff --cached --quiet' exits with 1 if there are staged changes, 0 otherwise
        result = subprocess.run(
            ["git", "-C", self.git.repo_path, "diff", "--cached", "--quiet"],
            capture_output=True
        )
        return result.returncode != 0

    def need_track_untracked(self, target: Optional[str] = None) -> bool:
        """Checks if there are any untracked files within a target that need to be tracked."""
        path_args = [target] if target else []
        untracked_files = self.git.run_git_text(["ls-files", "--others", "--exclude-standard"] + path_args)
        return bool(untracked_files.strip())


    def get_processed_diff(self, target: Optional[str] = None) -> List[DiffChunk]:
        """
        Converts a list of HunkWrapper objects (from a rename-aware diff)
        into the final list of DiffChunk objects for the synthesizer.
        """
        # Use the new, powerful diff function
        hunks = self.get_working_diff_with_renames(target)
        
        chunks: List[DiffChunk] = []
        processed_renames = set() # To handle cases with multiple hunks for one rename

        for h in hunks:
            # If this hunk is part of a rename AND we haven't created the
            # RenameDiffChunk for it yet, create it now.
            if h.is_rename and h.old_file_path not in processed_renames:
                chunks.append(RenameDiffChunk(
                    old_file_path=h.old_file_path,
                    new_file_path=h.new_file_path,
                    content=f"Rename: {h.old_file_path} -> {h.new_file_path}"
                ))
                processed_renames.add(h.old_file_path)
            
            # ALWAYS create a StandardDiffChunk for any hunk that contains line changes.
            # For a pure rename with no modifications, hunk_lines might be empty.
            if h.hunk_lines:
                chunks.append(StandardDiffChunk.from_patch(
                    file_path=h.new_file_path, # Modifications are always against the new path
                    patch_lines=h.hunk_lines,
                    old_start=h.old_start,
                    new_start=h.new_start
                ))
                
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

