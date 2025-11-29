# -----------------------------------------------------------------------------
# codestory - Dual Licensed Software
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


from .conftest import run_cli


class TestBasicCLI:
    def test_help(self, cli_exe):
        result = run_cli(cli_exe, ["--help"])
        assert result.returncode == 0
        assert "codestory" in result.stdout
        assert "Usage" in result.stdout

    def test_version(self, cli_exe):
        result = run_cli(cli_exe, ["--version"])
        assert result.returncode == 0
        # Version format might vary, but should contain version info
        assert result.stdout.strip()
