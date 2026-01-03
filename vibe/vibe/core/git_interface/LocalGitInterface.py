from pathlib import Path
import shutil
import subprocess
import re
import tempfile
from typing import Dict, List, Optional, Tuple, Union
from ..data.models import DiffChunk, CommitGroup, CommitResult, Addition, Removal
from .interface import GitInterface, HunkWrapper

class LocalGitInterface(GitInterface):
    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def run_git(self, args: List[str]) -> str:
        """Run git command and return stdout"""
        return subprocess.check_output(
            ["git", "-C", self.repo_path] + args,
            text=True,
            stderr=subprocess.DEVNULL,
            encoding="utf-8"
        )

    # -------------------------------
    # Core methods
    # -------------------------------

    def get_rename_map(self, target: Optional[str] = None, similarity: int = 50) -> Dict[str, str]:
        """
        Detect renames in the repo against HEAD.

        Args:
            target: optional file path or directory to limit detection
            similarity: rename similarity threshold (0-100)

        Returns:
            A dictionary mapping old_file_path -> new_file_path
        """
        path_args = [target] if target else []
        args = ["diff", f"-M{similarity}", "--name-status", "HEAD"] + path_args
        output = subprocess.check_output(
            ["git", "-C", self.repo_path] + args,
            text=True,
            stderr=subprocess.DEVNULL,
            encoding="utf-8"
        )

        rename_map: Dict[str, str] = {}
        for line in output.splitlines():
            # Format: R<score>  old/path  new/path
            if line.startswith("R"):
                parts = re.split(r"\s+", line.strip(), maxsplit=2)
                if len(parts) == 3:
                    _, old_path, new_path = parts
                    rename_map[old_path] = new_path

        return rename_map

    def get_working_diff(self, target: Optional[str] = None) -> List[HunkWrapper]:
        """
        Returns a list of raw hunks (file path, lines, old/new start).
        Does not produce DiffChunks or AI content.
        """
        path_args = [target] if target else []
        diff_output = self.run_git(["diff", "HEAD", "--unified=0"] + path_args)
        return self._parse_hunks(diff_output)

    def commit_to_new_branch(self, group: CommitGroup) -> CommitResult:
        """
        Create a new branch from HEAD, apply the commit group as a commit,
        and clean up the temporary worktree.
        """
        safe_branch_name = group.branch_name.replace("/", "-")
        tmpdir = Path(tempfile.mkdtemp(prefix=f"wt-{safe_branch_name}-"))

        try:
            # 1. Create worktree + branch
            subprocess.run(
                ["git", "-C", self.repo_path, "worktree", "add", "-b", group.branch_name, str(tmpdir), "HEAD"],
                check=True,
                capture_output=True
            )

            # 2. Apply patch to index inside worktree
            patch_text = group.to_patch()
            subprocess.run(
                ["git", "-C", str(tmpdir), "apply", "--cached", "--unidiff-zero"],
                input=patch_text,
                text=True,
                check=True
            )

            # 3. Commit
            commit_message = group.commmit_message
            if group.extended_message is not None:
                commit_message += f"\n{group.extended_message}"

            commit_output = subprocess.check_output(
                ["git", "-C", str(tmpdir), "commit", "-m", commit_message],
                text=True
            )

            match = re.search(r"\[.* ([a-f0-9]+)\]", commit_output)
            commit_hash = match.group(1) if match else ""

            return CommitResult(commit_hash=commit_hash, group=group)

        finally:
            # 4. Clean up worktree registration and directory
            try:
                subprocess.run(
                    ["git", "-C", self.repo_path, "worktree", "remove", "--force", str(tmpdir)],
                    check=True,
                    capture_output=True
                )
            except Exception as e:
                print(f"Warning: failed to remove worktree: {e}")

            shutil.rmtree(tmpdir, ignore_errors=True)

    def reset(self) -> None:
        """Reset staged changes (keeping working directory intact)"""
        subprocess.run(["git", "-C", self.repo_path, "reset"], check=True)

    def track_untracked(self, target: Optional[str] = None) -> None:
        """
        Make untracked files tracked without staging their content, using 'git add -N'.
        """
        if target:
            subprocess.run(
                ["git", "-C", self.repo_path, "add", "-N", target],
                check=True
            )
        else:
            # Track all untracked files
            untracked = self.run_git(["ls-files", "--others", "--exclude-standard"]).splitlines()
            if not untracked:
                return
            subprocess.run(
                ["git", "-C", self.repo_path, "add", "-N"] + untracked,
                check=True
            )

    def need_reset(self) -> bool:
        """Checks if there are staged changes that need to be reset"""
        # 'git diff --cached --quiet' exits with 1 if there are staged changes, 0 otherwise
        result = subprocess.run(
            ["git", "-C", self.repo_path, "diff", "--cached", "--quiet"],
            capture_output=True
        )
        return result.returncode != 0

    def need_track_untracked(self, target: Optional[str] = None) -> bool:
        """Checks if there are any untracked files within a target that need to be tracked."""
        path_args = [target] if target else []
        untracked_files = self.run_git(["ls-files", "--others", "--exclude-standard"] + path_args)
        return bool(untracked_files.strip())

    # -------------------------------
    # Internal parsing
    # -------------------------------

    def _parse_hunks(self, diff_output: str) -> List[HunkWrapper]:
        """
        Convert git diff output into structured hunk metadata.
        Each HunkWrapper contains:
            - file_path
            - hunk_lines
            - old_start
            - new_start
        """
        hunks: List[HunkWrapper] = []
        file_blocks = diff_output.split("\ndiff --git ")

        for block in file_blocks:
            if not block.strip():
                continue
            block = "diff --git " + block if not block.startswith("diff --git") else block
            lines = block.splitlines()

            # Extract file path
            path = None
            for line in lines:
                if line.startswith("+++ b/"):
                    path = line[6:]
                    break
            if not path:
                continue

            # Find hunks in file block
            hunk_start = None
            for i, line in enumerate(lines):
                if line.startswith("@@ "):
                    if hunk_start is not None:
                        hunks.append(HunkWrapper(
                            file_path=path,
                            hunk_lines=lines[hunk_start+1:i],
                            old_start=self._parse_hunk_start(lines[hunk_start])[0],
                            new_start=self._parse_hunk_start(lines[hunk_start])[1],
                        ))
                    hunk_start = i
            if hunk_start is not None:
                hunks.append(HunkWrapper(
                    file_path=path,
                    hunk_lines=lines[hunk_start+1:],
                    old_start=self._parse_hunk_start(lines[hunk_start])[0],
                    new_start=self._parse_hunk_start(lines[hunk_start])[1],
                ))

        return hunks

    @staticmethod
    def _parse_hunk_start(header_line: str) -> Tuple[int, int]:
        """
        Extract old_start and new_start from @@ -x,y +a,b @@ header
        """
        import re
        match = re.search(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", header_line)
        if match:
            return int(match.group(1)), int(match.group(2))
        return 0, 0
