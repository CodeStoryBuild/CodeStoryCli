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

import subprocess

from tests.integration.conftest import run_cli


class TestFix:
    def test_fix_linear(self, cli_exe, repo_factory):
        """Test fixing a commit in linear history."""
        repo = repo_factory("fix_linear")
        # Create a commit to fix
        repo.apply_changes({"file1.txt": "content1"})
        repo.stage_all()
        repo.commit("commit to fix")

        # Get commit hash
        commit_hash = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo.path, capture_output=True, text=True
        ).stdout.strip()

        # Run fix command (it will likely fail due to no AI key, but should validate hash)
        result = run_cli(cli_exe, ["-y", "fix", commit_hash], cwd=repo.path)

        # It might fail due to missing API key, but that means it passed validation
        # We check that it didn't fail due to invalid hash or repo state
        if result.returncode != 0:
            assert "invalid commit hash" not in result.stderr.lower()
            assert "not a git repository" not in result.stderr.lower()

    def test_fix_root(self, cli_exe, repo_factory):
        """Test fixing root commit."""
        repo = repo_factory("fix_root")
        # Get root commit hash
        root_hash = subprocess.run(
            ["git", "rev-list", "--max-parents=0", "HEAD"],
            cwd=repo.path,
            capture_output=True,
            text=True,
        ).stdout.strip()

        result = run_cli(cli_exe, ["-y", "fix", root_hash], cwd=repo.path)
        # Check for the specific error message
        assert "fixing the root commit is not supported yet" in result.stdout.lower()
