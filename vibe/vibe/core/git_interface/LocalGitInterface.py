import subprocess
import re
from typing import List, Optional, Union
from ..data.models import DiffChunk, CommitGroup, CommitResult, Addition, Removal
from .interface import GitInterface

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

    def get_working_diff(self, target: Optional[str] = None) -> List[DiffChunk]:
        """
        Get working diff against HEAD, zero-context hunks.
        Converts output into DiffChunks with patch info.
        """
        path_args = [target] if target else []
        diff_output = self.run_git(["diff", "HEAD", "--unified=0"] + path_args)
        return self._parse_diff(diff_output)

    def commit(self, group: CommitGroup) -> CommitResult:
        """
        Apply patch to index and create commit.
        """
        # Apply patch to index
        patch_text = group.to_patch()
        subprocess.run(
            ["git", "-C", self.repo_path, "apply", "--cached", "--unidiff-zero"],
            input=patch_text,
            text=True,
            check=True
        )

        # Commit
        commit_message = group.commmit_message
        if group.extended_message is not None:
            commit_message += f"\n{group.extended_message}" 

        # Run git commit and extract the commit hash from the output
        commit_output = self.run_git(["commit", "-m", commit_message])
        # Extract commit hash using regex from output like: "[master abcdef1] message"
        import re
        match = re.search(r"\[.* ([a-f0-9]+)\]", commit_output)
        commit_hash = match.group(1) if match else ""
        return CommitResult(commit_hash=commit_hash, group=group)

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

    def _parse_diff(self, diff_output: str) -> List[DiffChunk]:
        """
        Parse git diff output into DiffChunk objects.
        """
        chunks: List[DiffChunk] = []
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

            # Extract hunks
            hunk_start = None
            for i, line in enumerate(lines):
                if line.startswith("@@ "):
                    if hunk_start is not None:
                        chunks.append(self._build_hunk(path, lines[hunk_start:i]))
                    hunk_start = i
            if hunk_start is not None:
                chunks.append(self._build_hunk(path, lines[hunk_start:]))

        return chunks

    def _build_hunk(self, file_path: str, hunk_lines: List[str]) -> DiffChunk:
        """
        Build a DiffChunk from hunk lines.
        Preserves patch, line numbers, and content for to_patch().
        """
        header_line = hunk_lines[0]
        
        # Use a robust regex to capture optional line counts.
        match = re.search(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", header_line)

        if match:
            old_start = int(match.group(1))
            # Default to 1 if the line count is omitted, otherwise use the captured value.
            new_start = int(match.group(3))

        else:
            old_start = new_start = 0

        # Parse AI-legible content
        ai_content: List[Union[Addition, Removal]] = []
        current_old_line = old_start
        current_new_line = new_start

        # Iterate over hunk lines, starting after the header
        for line in hunk_lines[1:]:
            if line.startswith('+'):
                ai_content.append(Addition(content=line[1:], line_number=current_new_line))
                current_new_line += 1
            elif line.startswith('-'):
                ai_content.append(Removal(content=line[1:], line_number=current_old_line))
                current_old_line += 1
            else:
                # This handles context lines, which should increment both line counters
                current_old_line += 1
                current_new_line += 1
        
        # The raw content with +/- prefixes is still needed for git apply
        raw_content = "\n".join(hunk_lines[1:])

        return DiffChunk(
            file_path=file_path,
            content=raw_content,
            ai_content=ai_content,
            old_start=old_start,
            new_start=new_start,
        )