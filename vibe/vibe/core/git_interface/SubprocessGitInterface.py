from typing import List, Optional, Dict
import subprocess
from .interface import GitInterface


class SubprocessGitInterface(GitInterface):
    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def run_git_text(
        self,
        args: List[str],
        input_text: Optional[str] = None,
        env: Optional[Dict] = None,
    ) -> str:
        result = subprocess.run(
            ["git", "-C", self.repo_path] + args,
            input=input_text,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=True,
            env=env,
        )
        return result.stdout

    def run_git_binary(
        self,
        args: List[str],
        input_bytes: Optional[bytes] = None,
        env: Optional[Dict] = None,
    ) -> bytes:
        result = subprocess.run(
            ["git", "-C", self.repo_path] + args,
            input=input_bytes,
            text=False,
            encoding=None,
            capture_output=True,
            check=True,
            env=env,
        )
        return result.stdout
