# -----------------------------------------------------------------------------
# dslate - Dual Licensed Software
# Copyright (c) 2025 Adem Can
#
# This file is part of DSLATE.
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


import subprocess
from .conftest import run_cli


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
