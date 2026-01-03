# vibe/core/git_interface/subprocess_git.py

from pathlib import Path
from typing import List, Optional, Dict, Union
import subprocess
from .interface import GitInterface


class SubprocessGitInterface(GitInterface):
    def __init__(self, repo_path: Union[str, Path] = None):
        # Ensure repo_path is a Path object for consistency
        self.repo_path = Path(repo_path) if repo_path else Path(".")

    def run_git_text(
        self,
        args: List[str],
        input_text: Optional[str] = None,
        env: Optional[Dict] = None,
        cwd: Optional[Union[str, Path]] = None,
    ) -> Optional[str]:
        # This method is not used by the synthesizer, but included for completeness
        try:
            effective_cwd = str(cwd) if cwd is not None else str(self.repo_path)
            result = subprocess.run(
                ["git"] + args,
                input=input_text,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=True,
                env=env,
                cwd=effective_cwd,
            )
            return result.stdout
        except subprocess.CalledProcessError:
            return None

    def run_git_binary(
        self,
        args: List[str],
        input_bytes: Optional[bytes] = None,
        env: Optional[Dict] = None,
        cwd: Optional[Union[str, Path]] = None,
    ) -> Optional[bytes]:
        try:
            effective_cwd = str(cwd) if cwd is not None else str(self.repo_path)

            cmd = ["git"] + args

            result = subprocess.run(
                cmd,
                input=input_bytes,
                text=False,
                encoding=None,
                capture_output=True,
                check=True,
                env=env,
                cwd=effective_cwd,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            return None
