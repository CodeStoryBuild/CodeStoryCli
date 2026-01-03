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

from pathlib import Path
from unittest.mock import Mock, patch

from codestory.context import (
    GlobalConfig,
    GlobalContext,
)

# -----------------------------------------------------------------------------
# GlobalConfig Tests
# -----------------------------------------------------------------------------


def test_global_config_defaults():
    """Test that GlobalConfig has expected default values."""
    config = GlobalConfig()
    assert config.model == "no-model"
    assert config.api_key is None
    assert config.temperature == 0
    assert config.verbose is False
    assert config.auto_accept is False


def test_global_config_custom_values():
    """Test setting custom values in GlobalConfig."""
    config = GlobalConfig(
        model="openai/gpt-4",
        api_key="sk-test",
        temperature=0.5,
        verbose=True,
        auto_accept=True,
    )
    assert config.model == "openai/gpt-4"
    assert config.api_key == "sk-test"
    assert config.temperature == 0.5
    assert config.verbose is True
    assert config.auto_accept is True


# -----------------------------------------------------------------------------
# GlobalContext Tests
# -----------------------------------------------------------------------------


@patch("codestory.context.GitInterface")
@patch("codestory.context.GitCommands")
def test_global_context_from_config_defaults(mock_git_commands, mock_git_interface):
    """Test creating GlobalContext from an empty GlobalConfig (defaults)."""

    mock_interface_instance = Mock()
    mock_git_interface.return_value = mock_interface_instance

    mock_commands_instance = Mock()
    mock_git_commands.return_value = mock_commands_instance

    # Execute
    config = GlobalConfig()
    repo_path = Path("/tmp/repo")
    context = GlobalContext.from_global_config(config, repo_path)

    # Verify
    assert context.repo_path == repo_path
    assert context.get_model() is None
    assert context.git_interface == mock_interface_instance
    assert context.git_commands == mock_commands_instance
    assert context.config.verbose is False
    assert context.config.temperature == 0
    assert context.config.auto_accept is False

    # Verify calls
    mock_git_interface.assert_called_once_with(repo_path)
    mock_git_commands.assert_called_once_with(mock_interface_instance)


@patch("codestory.context.GitInterface")
@patch("codestory.context.GitCommands")
def test_global_context_from_config_custom(mock_git_commands, mock_git_interface):
    """Test creating GlobalContext from a populated GlobalConfig."""
    # Execute
    config = GlobalConfig(
        model="anthropic/claude-3",
        api_key="sk-ant",
        temperature=0.2,
        chunking_level="none",
        verbose=True,
        auto_accept=True,
        secret_scanner_aggression="none",
        silent=True,
    )
    repo_path = Path("/tmp/repo")
    context = GlobalContext.from_global_config(config, repo_path)

    # Verify
    assert context.get_model() is not None
    assert context.config.verbose is True
    assert context.config.temperature == 0.2
    assert context.config.chunking_level == "none"
    assert context.config.auto_accept is True
    assert context.config.secret_scanner_aggression == "none"
    assert context.config.silent is True
