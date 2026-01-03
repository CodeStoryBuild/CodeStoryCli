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

import pytest

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


def assert_flag_in_help(stdout, flag):
    """Helper to check for a flag in help output, handling potential truncation."""
    if flag.startswith("--") and len(flag) > 15:
        # Check for a significant prefix if the full flag is not found
        # Typer/Rich might truncate long flags with an ellipsis (...) or unicode ellipsis (…)
        prefix = flag[:15]
        assert prefix in stdout, f"Flag prefix {prefix} not found in help output"
    else:
        assert flag in stdout, f"Flag {flag} not found in help output"


class TestAPIBackwardCompatibility:
    @pytest.mark.parametrize(
        "flag",
        [
            "--version",
            "-V",
            "--log-dir",
            "-LD",
            "--supported-languages",
            "-SL",
            "--supported-providers",
            "-SP",
            "--repo",
            "--branch",
            "--custom-config",
            "--model",
            "--api-key",
            "--api-base",
            "--temperature",
            "--max-tokens",
            "--relevance-filtering",
            "--relevance-filter-similarity-threshold",
            "--secret-scanner-aggression",
            "--fallback-grouping-strategy",
            "--chunking-level",
            "--verbose",
            "-v",
            "--yes",
            "-y",
            "--silent",
            "-s",
            "--ask-for-commit-message",
            "--display-diff-type",
            "--batching-strategy",
            "--custom-embedding-model",
            "--cluster-strictness",
            "--num-retries",
        ],
    )
    def test_global_api(self, cli_exe, flag):
        """Verify that all global flags exist in the help text."""
        result = run_cli(cli_exe, ["--help"])
        assert result.returncode == 0
        assert_flag_in_help(result.stdout, flag)

    @pytest.mark.parametrize(
        "flag",
        [
            "-m",
            "--intent",
            "--fail-on-syntax-errors",
        ],
    )
    def test_commit_api(self, cli_exe, flag):
        """Verify that all commit flags exist in the help text."""
        result = run_cli(cli_exe, ["commit", "--help"])
        assert result.returncode == 0
        assert_flag_in_help(result.stdout, flag)

    @pytest.mark.parametrize(
        "flag",
        [
            "--start",
            "-m",
        ],
    )
    def test_fix_api(self, cli_exe, flag):
        """Verify that all fix flags exist in the help text."""
        result = run_cli(cli_exe, ["fix", "--help"])
        assert result.returncode == 0
        assert_flag_in_help(result.stdout, flag)

    @pytest.mark.parametrize(
        "flag",
        [
            "--ignore",
            "--min-size",
        ],
    )
    def test_clean_api(self, cli_exe, flag):
        """Verify that all clean flags exist in the help text."""
        result = run_cli(cli_exe, ["clean", "--help"])
        assert result.returncode == 0
        assert_flag_in_help(result.stdout, flag)
