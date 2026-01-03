from vibe.core.data.diff_chunk import DiffChunk
from dataclasses import dataclass
from typing import Optional, List, Dict
import json

@dataclass(init=False)
class RenameDiffChunk(DiffChunk):
    """
    Represents a rename diff chunk for Git apply.
    Stores old/new file paths and raw delete+add patch.
    Automatically computes LCS-based minimal changes.
    """

    old_file_path: str
    new_file_path: str
    content: str  # delete+add patch
    changes: List[Dict] = None 

    def __init__(self, old_file_path : str, new_file_path : str, content : str):        
        self.old_file_path = old_file_path
        self.new_file_path = new_file_path
        self.content = content

        old_lines, new_lines = [], []
        for line in self.content.splitlines():
            if line.startswith('-') and not line.startswith('---'):
                old_lines.append(line[1:])
            elif line.startswith('+') and not line.startswith('+++'):
                new_lines.append(line[1:])

        self.changes = self.diff_lines(old_lines, new_lines)

    def to_patch(self) -> str:
        patch_body = self.content
        # ensure trailing newline
        if not patch_body.endswith("\n"):
            patch_body += "\n"
        return patch_body

    def format_json(self) -> str:
        data = {
            "type": "Rename",
            "old_file_path": self.old_file_path,
            "new_file_path": self.new_file_path,
            "changes": self.changes
        }
        return json.dumps(data, indent=2)

    @staticmethod
    def diff_lines(old: List[str], new: List[str]) -> List[Dict]:
        n, m = len(old), len(new)
        dp = [[0]*(m+1) for _ in range(n+1)]
        for i in range(n):
            for j in range(m):
                if old[i] == new[j]:
                    dp[i+1][j+1] = dp[i][j] + 1
                else:
                    dp[i+1][j+1] = max(dp[i][j+1], dp[i+1][j])

        i, j = n, m
        changes = []
        while i > 0 and j > 0:
            if old[i-1] == new[j-1]:
                i -= 1
                j -= 1
            elif dp[i-1][j] >= dp[i][j-1]:
                changes.append({"type": "Removal", "content": old[i-1]})
                i -= 1
            else:
                changes.append({"type": "Addition", "content": new[j-1]})
                j -= 1
        while i > 0:
            changes.append({"type": "Removal", "content": old[i-1]})
            i -= 1
        while j > 0:
            changes.append({"type": "Addition", "content": new[j-1]})
            j -= 1
        return list(reversed(changes))
