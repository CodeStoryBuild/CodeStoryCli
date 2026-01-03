import subprocess
from typing import List, Optional
from vibe.core.data.models import HunkChunk, FileDiff

class GitDiffExtractor:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def run_git(self, args: List[str]) -> str:
        return subprocess.check_output(
            ["git", "-C", self.repo_path] + args,
            text=True,
            stderr=subprocess.DEVNULL
        )

    def extract_file_diffs(self, target: Optional[str] = None) -> List[FileDiff]:
        """
        Returns a list of FileDiff objects, each containing valid HunkChunks.
        Each HunkChunk is valid and can be applied with git apply.
        """
        path_args = [target] if target else []
        diff_output = self.run_git(["diff", "HEAD", "--unified=0"] + path_args)
        return self.parse_diff_output(diff_output)

    def parse_diff_output(self, diff_output: str) -> List[FileDiff]:
        file_blocks = diff_output.split("\ndiff --git ")
        results: List[FileDiff] = []

        for block in file_blocks:
            if not block.strip():
                continue
            block = "diff --git " + block if not block.startswith("diff --git") else block
            lines = block.splitlines()

            # Extract file headers
            file_header_lines = []
            path = None
            for line in lines:
                if line.startswith("diff --git ") or line.startswith("--- ") or line.startswith("+++ "):
                    file_header_lines.append(line)
                    if line.startswith("+++ b/"):
                        path = line[6:]
            if not path:
                continue

            # Extract hunks
            hunks: List[HunkChunk] = []
            hunk_start = None
            for i, line in enumerate(lines):
                if line.startswith("@@ "):
                    if hunk_start is not None:
                        hunks.append(self.build_hunk(file_header_lines, lines[hunk_start:i]))
                    hunk_start = i
            if hunk_start is not None:
                hunks.append(self.build_hunk(file_header_lines, lines[hunk_start:]))

            results.append(FileDiff(path=path, hunks=hunks))
        return results

    def build_hunk(self, file_header_lines: List[str], hunk_lines: List[str]) -> HunkChunk:
        patch = "\n".join(file_header_lines + hunk_lines)
        header = hunk_lines[0]
        human_readable = "\n".join(line for line in hunk_lines if line.startswith("+") or line.startswith("-"))
        return HunkChunk(header=header, patch=patch, human_readable=human_readable)
