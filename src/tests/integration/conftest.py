# -----------------------------------------------------------------------------
# /*
#  * Copyright (C) 2025 CodeStory
#  *
#  * This program is free software; you can redistribute it and/or modify
#  * it under the terms of the GNU General Public License as published by
#  * the Free Software Foundation; Version 2.
#  *
#  * This program is distributed in the hope that it will be useful,
#  * but WITHOUT ANY WARRANTY; without even the implied warranty of
#  * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  * GNU General Public License for more details.
#  *
#  * You should have received a copy of the GNU General Public License
#  * along with this program; if not, you can contact us at support@codestory.build
#  */
# -----------------------------------------------------------------------------

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from tests.integration.repo_utils import RepoState

# Get executable path from environment variable
_RAW_CLI_PATH = os.environ.get("CLI_ARTIFACT_PATH")

# Convert to absolute path immediately so it works regardless of cwd
CLI_EXE = os.path.abspath(_RAW_CLI_PATH) if _RAW_CLI_PATH else None


@pytest.fixture(scope="session")
def cli_exe():
    if not CLI_EXE:
        pytest.skip("CLI_ARTIFACT_PATH not set")

    # Check if it's a python command or a file
    if not CLI_EXE.startswith("python"):
        if not os.path.exists(CLI_EXE):
            pytest.fail(f"Executable not found at {CLI_EXE}")

        # Ensure executable permissions on Linux/macOS
        if sys.platform in ("linux", "darwin"):
            subprocess.run(["chmod", "+x", CLI_EXE], check=True)

    return CLI_EXE


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def git_repo(temp_dir):
    subprocess.run(["git", "init", "-b", "main"], cwd=temp_dir, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=temp_dir, check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=temp_dir, check=True
    )
    # Initial commit to avoid empty repo issues
    (temp_dir / ".gitignore").write_text("__pycache__/")
    subprocess.run(["git", "add", "."], cwd=temp_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=temp_dir, check=True)
    return temp_dir


@pytest.fixture
def repo_factory(temp_dir):
    """Fixture to create RepoState instances."""

    def _create_repo(subdir="repo"):
        path = temp_dir / subdir
        repo = RepoState(path)
        repo.setup_repo()
        return repo

    return _create_repo


def run_cli(exe, args, cwd=None, env=None, input_str=None):
    """Helper to run the CLI executable."""
    cmd = [exe] if not exe.startswith("python") else exe.split()

    cmd.append("--model")
    cmd.append("no-model")
    cmd.append("--yes")

    cmd.extend(args)

    # Ensure we capture output
    result = subprocess.run(
        cmd,
        cwd=cwd,
        env=env or os.environ.copy(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        input=input_str,
    )
    return result
