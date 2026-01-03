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

import pytest

from tests.integration.conftest import run_cli


class TestCommitScenarios:
    @pytest.mark.parametrize(
        "scenario_name, changes",
        [
            ("new_file", {"new_file.txt": "new content"}),
            (
                "deleted_file",
                {"README.md": None},
            ),  # Assuming README.md exists from setup
            ("modified_file", {"README.md": "modified content"}),
            ("renamed_file", {"README.md": ("README.md", "README_renamed.md")}),
            (
                "renamed_modified",
                {
                    "README.md": ("README.md", "README_renamed.md"),
                    "README_renamed.md": "modified content",
                },
            ),
            ("binary_new", {"data.bin": b"\x00\x01\x02"}),
            (
                "mixed_changes",
                {
                    "new_file.txt": "new content",
                    "README.md": "modified content",
                    "data.bin": b"\x00\x01\x02",
                },
            ),
            (
                "complex_refactor",
                {
                    "src/old_module.py": (
                        "src/old_module.py",
                        "src/new_module/renamed.py",
                    ),
                    "src/new_module/renamed.py": "updated content in renamed file",
                    "src/unused.py": None,
                    "docs/readme.txt": "documentation update",
                },
            ),
            (
                "deep_nested",
                {
                    "a/b/c/d/e/f/deep.txt": "deep content",
                    "x/y/z/other.txt": "other deep content",
                },
            ),
            ("large_batch", {f"file_{i}.txt": f"content {i}" for i in range(20)}),
        ],
    )
    def test_commit_scenarios(self, cli_exe, repo_factory, scenario_name, changes):
        """Test commit command with various file state scenarios."""
        repo = repo_factory(f"repo_{scenario_name}")

        repo.apply_changes(changes)

        # Get expected tree hash (what the repo looks like now)
        expected_tree = repo.get_current_tree()

        # Run commit command
        # We expect it to fail due to missing API key, but we verify it doesn't corrupt the repo.
        result = run_cli(cli_exe, ["-y", "commit"], cwd=repo.path)

        # If we use --help, it should succeed (return 0) and NOT modify the repo.
        # This confirms the command parsing works and it doesn't crash on these file states.
        assert result.returncode == 0

        # Verify working directory state is preserved (matches expected tree)
        current_tree = repo.get_current_tree()
        assert current_tree == expected_tree, (
            f"Repo state changed unexpectedly in scenario {scenario_name}"
        )

    def test_commit_clean(self, cli_exe, repo_factory):
        repo = repo_factory("clean")
        result = run_cli(cli_exe, ["-y", "commit"], cwd=repo.path)
        assert result.returncode == 1

    def test_commit_on_different_branch(self, cli_exe, repo_factory):
        """Test committing changes on a branch that is not currently checked out."""
        repo = repo_factory("commit_branch")
        repo.create_branch("feature")

        # Make changes in working directory
        repo.apply_changes({"feature.txt": "feature content"})

        # Run commit on the 'feature' branch
        # Even if we are on 'main', it should work because we use index-only manipulation
        result = run_cli(
            cli_exe, ["-y", "--branch", "feature", "commit"], cwd=repo.path
        )
        assert result.returncode == 0

        # Verify 'feature' branch was updated
        feature_hash = repo.get_commit_hash("feature")
        main_hash = repo.get_commit_hash("main")
        assert feature_hash != main_hash

        # Verify content on feature branch
        repo.checkout("feature")
        assert (repo.path / "feature.txt").exists()

    def test_commit_specific_target(self, cli_exe, repo_factory):
        """Test committing only a specific directory."""
        repo = repo_factory("commit_target")
        repo.apply_changes(
            {
                "src/app.py": "print('app')",
                "docs/readme.md": "docs",
            }
        )

        # Commit only 'src'
        result = run_cli(cli_exe, ["-y", "commit", "src"], cwd=repo.path)
        assert result.returncode == 0

        # Verify that only src/app.py was committed by running commit again.
        # If 'docs/readme.md' was also committed, the second run will say "No changes to process".
        result2 = run_cli(cli_exe, ["-y", "commit"], cwd=repo.path)
        assert result2.returncode == 0
        assert "no changes to process" not in result2.stdout.lower()

    def test_commit_detached(self, cli_exe, repo_factory):
        repo = repo_factory("detached")
        subprocess.run(
            ["git", "checkout", "--detach", "HEAD"], cwd=repo.path, check=True
        )
        result = run_cli(cli_exe, ["-y", "commit"], cwd=repo.path)
        assert "detached head" in result.stderr.lower()
