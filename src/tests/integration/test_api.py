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

from tests.integration.conftest import run_cli


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
