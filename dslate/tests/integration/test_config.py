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


import os
import subprocess
from pathlib import Path

import pytest

from tests.integration.conftest import run_cli


class TestConfigCommand:
    """Test the config command with various scenarios."""

    def test_config_help(self, cli_exe, temp_dir):
        """Test that config --help works."""
        result = run_cli(cli_exe, ["config", "--help"], cwd=temp_dir)
        assert result.returncode == 0
        assert "config" in result.stdout.lower()
        assert "configuration" in result.stdout.lower()

    def test_config_set_local(self, cli_exe, temp_dir):
        """Test setting a local configuration value."""
        # Create a .gitignore first
        gitignore = temp_dir / ".gitignore"
        gitignore.write_text("*.pyc\n")

        result = run_cli(
            cli_exe, ["config", "model", "gemini:gemini-2.0-flash"], cwd=temp_dir
        )
        assert result.returncode == 0

        # Verify config file was created
        config_file = temp_dir / "dslateconfig.toml"
        assert config_file.exists()

        # Verify content
        content = config_file.read_text()
        assert "model" in content
        assert "gemini:gemini-2.0-flash" in content

        # Verify .gitignore was updated
        gitignore_content = gitignore.read_text()
        assert "dslateconfig.toml" in gitignore_content

    def test_config_set_local_no_gitignore(self, cli_exe, temp_dir):
        """Test setting local config when .gitignore doesn't exist."""
        result = run_cli(cli_exe, ["config", "temperature", "0.8"], cwd=temp_dir)
        assert result.returncode == 0

        # Verify config file was created
        config_file = temp_dir / "dslateconfig.toml"
        assert config_file.exists()

        # Verify warning was printed
        assert "warning" in result.stdout.lower() or "warning" in result.stderr.lower()

    def test_config_set_global(self, cli_exe, temp_dir):
        """Test setting a global configuration value."""
        result = run_cli(
            cli_exe, ["config", "temperature", "0.8", "--global"], cwd=temp_dir
        )
        assert result.returncode == 0
        assert "set temperature = 0.8 (global)" in result.stdout.lower()
        assert "config file: " in result.stdout.lower()

    def test_config_set_env(self, cli_exe, temp_dir):
        """Test getting environment variable instructions."""
        result = run_cli(
            cli_exe, ["config", "api_key", "test-key", "--env"], cwd=temp_dir
        )
        assert result.returncode == 0
        # Should print instructions, not create a file
        assert (
            "environment" in result.stdout.lower() or "export" in result.stdout.lower()
        )
        assert "dslate_api_key" in result.stdout.lower()

    def test_config_get_local(self, cli_exe, temp_dir):
        """Test getting a local configuration value."""
        # First set a value
        run_cli(cli_exe, ["config", "model", "test-model"], cwd=temp_dir)

        # Then get it
        result = run_cli(cli_exe, ["config", "model"], cwd=temp_dir)
        assert result.returncode == 0
        assert "test-model" in result.stdout

    def test_config_get_all(self, cli_exe, temp_dir):
        """Test getting all configuration values."""
        # Set multiple values
        run_cli(cli_exe, ["config", "model", "test-model"], cwd=temp_dir)
        run_cli(cli_exe, ["config", "temperature", "0.5"], cwd=temp_dir)

        # Get all
        result = run_cli(cli_exe, ["config"], cwd=temp_dir)
        assert result.returncode == 0
        assert "model" in result.stdout
        assert "temperature" in result.stdout

    def test_config_update_existing(self, cli_exe, temp_dir):
        """Test updating an existing configuration value."""
        # Set initial value
        run_cli(cli_exe, ["config", "model", "initial-model"], cwd=temp_dir)

        # Update it
        result = run_cli(cli_exe, ["config", "model", "updated-model"], cwd=temp_dir)
        assert result.returncode == 0

        # Verify update
        config_file = temp_dir / "dslateconfig.toml"
        content = config_file.read_text()
        assert "updated-model" in content
        assert "initial-model" not in content

    def test_config_multiple_values(self, cli_exe, temp_dir):
        """Test setting multiple configuration values."""
        run_cli(cli_exe, ["config", "model", "test-model"], cwd=temp_dir)
        run_cli(cli_exe, ["config", "temperature", "0.7"], cwd=temp_dir)
        run_cli(cli_exe, ["config", "verbose", "true"], cwd=temp_dir)

        config_file = temp_dir / "dslateconfig.toml"
        content = config_file.read_text()

        assert "model" in content
        assert "temperature" in content
        assert "verbose" in content

    def test_config_gitignore_already_has_entry(self, cli_exe, temp_dir):
        """Test that we don't duplicate .gitignore entries."""
        # Create .gitignore with config file already in it
        gitignore = temp_dir / ".gitignore"
        gitignore.write_text("dslateconfig.toml\n*.pyc\n")

        run_cli(cli_exe, ["config", "model", "test"], cwd=temp_dir)

        # Verify no duplication
        gitignore_content = gitignore.read_text()
        assert gitignore_content.count("dslateconfig.toml") == 1

    def test_config_invalid_both_scopes(self, cli_exe, temp_dir):
        """Test that specifying both --global and --env fails."""
        result = run_cli(
            cli_exe,
            ["config", "model", "test", "--global", "--env"],
            cwd=temp_dir,
        )
        assert result.returncode != 0
        assert "error" in result.stdout.lower() or "error" in result.stderr.lower()

    def test_config_get_nonexistent(self, cli_exe, temp_dir):
        """Test getting a non-existent configuration key."""
        result = run_cli(cli_exe, ["config", "nonexistent_key"], cwd=temp_dir)
        assert result.returncode == 1
        assert "unknown configuration key" in result.stdout.lower()
        assert "available configuration options" in result.stdout.lower()

    def test_config_preserves_other_values(self, cli_exe, temp_dir):
        """Test that setting a value preserves other existing values."""
        # Set multiple values
        run_cli(cli_exe, ["config", "model", "model1"], cwd=temp_dir)
        run_cli(cli_exe, ["config", "temperature", "0.5"], cwd=temp_dir)

        # Update one value
        run_cli(cli_exe, ["config", "model", "model2"], cwd=temp_dir)

        # Verify both values exist and temperature is unchanged
        config_file = temp_dir / "dslateconfig.toml"
        content = config_file.read_text()
        assert "model2" in content
        assert "0.5" in content and "temperature" in content
