# -----------------------------------------------------------------------------
# dslate - Dual Licensed Software
# Copyright (c) 2025 Adem Can
#
# This file is part of codestory.
#
# codestory is available under a dual-license:
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


from abc import ABC, abstractmethod
from pathlib import Path
from subprocess import CompletedProcess


class GitInterface(ABC):
    """
    Abstract interface for running git commands.
    This abstracts away the details of how git commands are executed.
    """

    @abstractmethod
    def run_git_text_out(
        self,
        args: list[str],
        input_text: str | None = None,
        env: dict | None = None,
        cwd: str | Path | None = None,
    ) -> str | None:
        """Run a git command with text input/output. Returns None on error."""

    @abstractmethod
    def run_git_binary_out(
        self,
        args: list[str],
        input_bytes: bytes | None = None,
        env: dict | None = None,
        cwd: str | Path | None = None,
    ) -> bytes | None:
        """Run a git command with binary input/output. Returns None on error."""

    @abstractmethod
    def run_git_text(
        self,
        args: list[str],
        input_text: str | None = None,
        env: dict | None = None,
        cwd: str | Path | None = None,
    ) -> CompletedProcess[str] | None:
        """Run a git command with text response output. Returns None on error."""

    @abstractmethod
    def run_git_binary(
        self,
        args: list[str],
        input_bytes: bytes | None = None,
        env: dict | None = None,
        cwd: str | Path | None = None,
    ) -> CompletedProcess[bytes] | None:
        """Run a git command with binary response output. Returns None on error."""
