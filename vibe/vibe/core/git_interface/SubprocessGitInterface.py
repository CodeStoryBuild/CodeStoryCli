# vibe/core/git_interface/subprocess_git.py

from pathlib import Path
from typing import List, Optional, Dict, Union
import subprocess
from .interface import GitInterface


class SubprocessGitInterface(GitInterface):
    def __init__(self, repo_path: Union[str, Path]):
        # Ensure repo_path is a Path object for consistency
        self.repo_path = Path(repo_path)

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

            if "apply" in args:
                if input_bytes:
                    print(
                        f"DEBUG_INTERFACE: run_git_binary received {len(input_bytes)} bytes for 'git apply'."
                    )
                else:
                    print(
                        "DEBUG_INTERFACE: WARNING! run_git_binary received NO input bytes for 'git apply'."
                    )

            # The debug print can be simplified now
            print(f"DEBUG: Running command: {' '.join(cmd)}")
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
            print(
                f"DEBUG: Command succeeded, stdout length: {len(result.stdout)}, stderr length: {len(result.stderr)}"
            )
            if result.stderr:
                # Limit stderr printing to avoid flooding logs
                print(
                    f"DEBUG: stderr: {result.stderr.decode('utf-8', 'replace').strip()}"
                )
            if result.stdout:
                print(
                    f"DEBUG: stdout: {result.stdout.decode('utf-8', 'replace').strip()}"
                )
            return result.stdout
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Git command failed: {' '.join(e.cmd)}")
            print(f"ERROR: stderr: {e.stderr.decode('utf-8', 'replace').strip()}")
            return None
