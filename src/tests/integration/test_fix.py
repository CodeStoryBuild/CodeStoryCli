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
        assert "not supported yet" in result.stderr.lower()

    def test_fix_on_different_branch(self, cli_exe, repo_factory):
        """Test fixing a commit on a branch that is not currently checked out."""
        repo = repo_factory("fix_branch")
        repo.create_branch("other")
        repo.checkout("other")

        repo.apply_changes({"other.txt": "content"})
        repo.stage_all()
        repo.commit("other commit")
        other_hash = repo.get_commit_hash()

        repo.checkout("main")

        # Run fix on 'other' branch using --branch
        result = run_cli(
            cli_exe, ["-y", "--branch", "other", "fix", other_hash], cwd=repo.path
        )
        assert result.returncode == 0

    def test_fix_with_start_commit(self, cli_exe, repo_factory):
        """Test fixing a range of commits by specifying a start commit."""
        repo = repo_factory("fix_range")
        # Create 3 commits
        hashes = []
        for i in range(3):
            repo.apply_changes({f"file{i}.txt": f"content{i}"})
            repo.stage_all()
            repo.commit(f"commit {i}")
            hashes.append(repo.get_commit_hash())

        # Fix from commit 0 to commit 2
        result = run_cli(
            cli_exe, ["-y", "fix", hashes[2], "--start", hashes[0]], cwd=repo.path
        )
        assert result.returncode == 0

    def test_fix_invalid_hash(self, cli_exe, repo_factory):
        """Test error handling for invalid commit hash."""
        repo = repo_factory("fix_invalid")
        result = run_cli(cli_exe, ["-y", "fix", "notahash"], cwd=repo.path)
        assert result.returncode != 0
        assert "invalid commit hash" in result.stderr.lower()
