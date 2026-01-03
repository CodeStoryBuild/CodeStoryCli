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


import pytest
import subprocess
from .conftest import run_cli


class TestCommitScenarios:
    @pytest.mark.parametrize("scenario_name, changes", [
        ("new_file", {"new_file.txt": "new content"}),
        ("deleted_file", {"README.md": None}), # Assuming README.md exists from setup
        ("modified_file", {"README.md": "modified content"}),
        ("renamed_file", {"README.md": ("README.md", "README_renamed.md")}),
        ("renamed_modified", {"README.md": ("README.md", "README_renamed.md"), "README_renamed.md": "modified content"}),
        ("binary_new", {"data.bin": b"\x00\x01\x02"}),
        ("mixed_changes", {
            "new_file.txt": "new content",
            "README.md": "modified content",
            "data.bin": b"\x00\x01\x02"
        }),
        ("complex_refactor", {
            "src/old_module.py": ("src/old_module.py", "src/new_module/renamed.py"),
            "src/new_module/renamed.py": "updated content in renamed file",
            "src/unused.py": None,
            "docs/readme.txt": "documentation update"
        }),
        ("deep_nested", {
            "a/b/c/d/e/f/deep.txt": "deep content",
            "x/y/z/other.txt": "other deep content"
        }),
        ("large_batch", {f"file_{i}.txt": f"content {i}" for i in range(20)})
    ])
    def test_commit_scenarios(self, cli_exe, repo_factory, scenario_name, changes):
        """Test commit command with various file state scenarios."""
        repo = repo_factory(f"repo_{scenario_name}")
        
        # Apply changes
        # For renamed_modified, we need to handle it carefully if apply_changes isn't smart enough
        # Our simple apply_changes might need help. Let's adjust the test data or the helper if needed.
        # For now, let's assume apply_changes handles the dict iteration.
        # If we have a rename AND a modification to the new name, we need to ensure rename happens first
        # or just write to the new path.
        
        # Actually, for "renamed_modified", we can just rename, then modify the new file.
        # But apply_changes iterates. Let's split it if needed, or just define it as:
        # Rename README.md -> README_renamed.md
        # Then write to README_renamed.md
        # If the dict order is preserved (Python 3.7+), we can rely on that if we structure it right.
        # But for robustness, let's just use separate keys if possible or trust the helper.
        
        # Special handling for renamed_modified in the test setup if needed, 
        # but let's see if we can express it in the dict.
        # If we pass {"README.md": ("README.md", "new.md"), "new.md": "content"}, 
        # and iterate, if rename happens first, then write to new.md works.
        
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
        assert current_tree == expected_tree, f"Repo state changed unexpectedly in scenario {scenario_name}"

    def test_commit_clean(self, cli_exe, repo_factory):
        repo = repo_factory("clean")
        result = run_cli(cli_exe, ["-y", "commit"], cwd=repo.path)
        assert result.returncode != 0
        assert "no commits were created" in result.stdout.lower() or "no changes" in result.stdout.lower() or "clean" in result.stdout.lower()

    def test_commit_detached(self, cli_exe, repo_factory):
        repo = repo_factory("detached")
        subprocess.run(["git", "checkout", "--detach", "HEAD"], cwd=repo.path, check=True)
        result = run_cli(cli_exe, ["-y", "commit"], cwd=repo.path)
        assert result.returncode != 0
        assert "detached head" in result.stderr.lower() or "detached head" in result.stdout.lower()
