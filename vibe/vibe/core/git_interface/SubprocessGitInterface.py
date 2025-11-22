# vibe/core/git_interface/subprocess_git.py

import subprocess
from pathlib import Path

from loguru import logger

from .interface import GitInterface


class SubprocessGitInterface(GitInterface):
    def __init__(self, repo_path: str | Path | None = None) -> None:
        # Ensure repo_path is a Path object for consistency
        if isinstance(repo_path, Path):
            self.repo_path = repo_path
        else:
            self.repo_path = Path(repo_path)

    def run_git_text(
        self,
        args: list[str],
        input_text: str | None = None,
        env: dict | None = None,
        cwd: str | Path | None = None,
    ) -> str | None:
        # This method is not used by the synthesizer, but included for completeness
        try:
            effective_cwd = str(cwd) if cwd is not None else str(self.repo_path)
            cmd = ["git"] + args
            logger.debug(
                f"Running git text command: {' '.join(cmd)} cwd={effective_cwd}"
            )
            result = subprocess.run(
                cmd,
                input=input_text,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=True,
                env=env,
                cwd=effective_cwd,
            )
            if result.stdout:
                logger.debug(
                    f"git stdout (text): {result.stdout[:2000]}"
                    + ("...(truncated)" if len(result.stdout) > 2000 else "")
                )

            if result.stderr:
                logger.debug(
                    f"git stderr (text): {result.stderr[:2000]}"
                    + ("...(truncated)" if len(result.stderr) > 2000 else "")
                )
            logger.debug(f"git returncode: {result.returncode}")
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(
                f"Git text command failed: {' '.join(e.cmd)} code={e.returncode} stderr={e.stderr}"
            )
            return None

    def run_git_binary(
        self,
        args: list[str],
        input_bytes: bytes | None = None,
        env: dict | None = None,
        cwd: str | Path | None = None,
    ) -> bytes | None:
        try:
            effective_cwd = str(cwd) if cwd is not None else str(self.repo_path)

            cmd = ["git"] + args
            logger.debug(
                f"Running git binary command: {' '.join(cmd)} cwd={effective_cwd}"
            )

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
            if result.stdout:
                logger.debug(f"git stdout (binary length): {len(result.stdout)} bytes")
            if result.stderr:
                logger.debug(
                    f"git stderr (binary): {result.stderr[:2000]!r}"
                    + ("...(truncated)" if len(result.stderr) > 2000 else "")
                )
            print(result.stdout)
            print(result.stderr)
            logger.debug(f"git returncode: {result.returncode}")
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(
                f"Git binary command failed: {' '.join(e.cmd)} code={e.returncode} stderr={e.stderr.decode('utf-8', errors='ignore')}"
            )
            return None
