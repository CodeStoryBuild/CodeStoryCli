# -----------------------------------------------------------------------------
# dslate - Dual Licensed Software
# Copyright (c) 2025 Adem Can
#
# This file is part of DSLATE.
#
# DSLATE is available under a dual-license:
#   1. AGPLv3 (Affero General Public License v3)
#      - See LICENSE.txt and LICENSE-AGPL.txt
#      - Online: https://www.gnu.org/licenses/agpl-3.0.html
#
#   2. Commercial License
#      - For proprietary or revenue-generating use,
#        including SaaS, embedding in closed-source software,
#        or avoiding AGPL obligations.
#      - See LICENSE.txt and COMMERCIAL-LICENSE.txt
#      - Contact: ademfcan@gmail.com
#
# By using this file, you agree to the terms of one of the two licenses above.
# -----------------------------------------------------------------------------


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

    def run_git_text_out(
        self,
        args: list[str],
        input_text: str | None = None,
        env: dict | None = None,
        cwd: str | Path | None = None,
    ) -> str | None:
        result = self.run_git_text(args, input_text, env, cwd)
        return result.stdout if result else None

    def run_git_binary_out(
        self,
        args: list[str],
        input_bytes: bytes | None = None,
        env: dict | None = None,
        cwd: str | Path | None = None,
    ) -> bytes | None:
        result = self.run_git_binary(args, input_bytes, env, cwd)
        return result.stdout if result else None

    def run_git_text(
        self,
        args: list[str],
        input_text: str | None = None,
        env: dict | None = None,
        cwd: str | Path | None = None,
    ) -> subprocess.CompletedProcess[str] | None:
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
            return result
        except subprocess.CalledProcessError as e:
            logger.warning(
                f"Git text command failed: {' '.join(e.cmd)} code={e.returncode} stderr={e.stderr}"
            )
            return None

    def run_git_binary(
        self,
        args: list[str],
        input_bytes: bytes | None = None,
        env: dict | None = None,
        cwd: str | Path | None = None,
    ) -> subprocess.CompletedProcess[bytes] | None:
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
            logger.debug(f"git returncode: {result.returncode}")
            return result
        except subprocess.CalledProcessError as e:
            logger.warning(
                f"Git binary command failed: {' '.join(e.cmd)} code={e.returncode} stderr={e.stderr.decode('utf-8', errors='ignore')}"
            )
            return None
