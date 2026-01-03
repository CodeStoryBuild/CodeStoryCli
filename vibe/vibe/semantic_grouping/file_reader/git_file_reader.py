
from typing import Optional
from ...core.git_interface.interface import GitInterface

class GitFileReader:
    def __init__(self, git: GitInterface, base_commit: str, patched_commit: str):
        self.git = git
        self.base_commit = base_commit
        self.patched_commit = patched_commit

    def read(self, path: str, old_content: bool = False) -> Optional[str]:
        """
        Returns the file content from the specified commit using git cat-file.
        version: 'old' for base_commit, 'new' for patched_commit (HEAD by default)
        """
        commit = self.base_commit if old_content else self.patched_commit
        # Use git cat-file to get file content
        # rel_path should be in posix format for git
        rel_path_git = path.replace("\\", "/")
        obj = f"{commit}:{rel_path_git}"
        return self.git.run_git_text(["cat-file", "-p", obj])

