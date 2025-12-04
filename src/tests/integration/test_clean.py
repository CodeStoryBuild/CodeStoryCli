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
