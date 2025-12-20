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


class TestClean:
    def test_clean_repo(self, cli_exe, repo_factory):
        """Test cleaning a repo."""
        repo = repo_factory("clean_repo")
        # Create some commits
        for i in range(3):
            repo.apply_changes({f"file{i}.txt": f"content{i}"})
            repo.stage_all()
            repo.commit(f"commit{i}")

        # Run clean command (dry run or help to verify it starts)
        result = run_cli(cli_exe, ["-y", "clean"], cwd=repo.path)
        assert result.returncode == 0

        # Verify repo state is preserved
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo.path,
            capture_output=True,
            text=True,
        ).stdout
        assert not status.strip()

    def test_clean_on_different_branch(self, cli_exe, repo_factory):
        """Test cleaning history on a branch that is not currently checked out."""
        repo = repo_factory("clean_branch")
        repo.create_branch("to_clean")
        repo.checkout("to_clean")

        for i in range(3):
            repo.apply_changes({f"file{i}.txt": f"content{i}"})
            repo.stage_all()
            repo.commit(f"commit{i}")

        repo.checkout("main")

        # Run clean on 'to_clean' branch
        result = run_cli(
            cli_exe, ["-y", "--branch", "to_clean", "clean"], cwd=repo.path
        )
        assert result.returncode == 0

    def test_clean_with_start_from(self, cli_exe, repo_factory):
        """Test cleaning history starting from a specific commit."""
        repo = repo_factory("clean_start")
        hashes = []
        for i in range(5):
            repo.apply_changes({f"file{i}.txt": f"content{i}"})
            repo.stage_all()
            repo.commit(f"commit{i}")
            hashes.append(repo.get_commit_hash())

        # Clean starting from commit 2
        result = run_cli(cli_exe, ["-y", "clean", hashes[2]], cwd=repo.path)
        print(result.stdout)
        print(result.stderr)
        assert result.returncode == 0

    def test_clean_with_ignore(self, cli_exe, repo_factory):
        """Test cleaning history while ignoring specific commits."""
        repo = repo_factory("clean_ignore")
        hashes = []
        for i in range(3):
            repo.apply_changes({f"file{i}.txt": f"content{i}"})
            repo.stage_all()
            repo.commit(f"commit{i}")
            hashes.append(repo.get_commit_hash())

        # Clean while ignoring the second commit
        result = run_cli(cli_exe, ["-y", "clean", "--ignore", hashes[1]], cwd=repo.path)
        print(result.stdout)
        print(result.stderr)

        assert result.returncode == 0
