from pathlib import Path
from unittest.mock import Mock, patch

from codestory.context import (
    CleanContext,
    FixContext,
    GlobalConfig,
    GlobalContext,
)

# -----------------------------------------------------------------------------
# GlobalConfig Tests
# -----------------------------------------------------------------------------


def test_global_config_defaults():
    """Test that GlobalConfig has expected default values."""
    config = GlobalConfig()
    assert config.model is None
    assert config.api_key is None
    assert config.temperature == 0.7
    assert config.aggresiveness == "Regular"
    assert config.verbose is False
    assert config.auto_accept is False


def test_global_config_custom_values():
    """Test setting custom values in GlobalConfig."""
    config = GlobalConfig(
        model="openai:gpt-4",
        api_key="sk-test",
        temperature=0.5,
        aggresiveness="Extra",
        verbose=True,
        auto_accept=True,
    )
    assert config.model == "openai:gpt-4"
    assert config.api_key == "sk-test"
    assert config.temperature == 0.5
    assert config.aggresiveness == "Extra"
    assert config.verbose is True
    assert config.auto_accept is True


# -----------------------------------------------------------------------------
# GlobalContext Tests
# -----------------------------------------------------------------------------


@patch("codestory.context.SubprocessGitInterface")
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
    assert context.model is None
    assert context.git_interface == mock_interface_instance
    assert context.git_commands == mock_commands_instance
    assert context.verbose is False
    assert context.temperature == 0.7
    assert context.aggresiveness == "Regular"
    assert context.auto_accept is False

    # Verify calls
    mock_git_interface.assert_called_once_with(repo_path)
    mock_git_commands.assert_called_once_with(mock_interface_instance)


@patch("codestory.context.SubprocessGitInterface")
@patch("codestory.context.GitCommands")
def test_global_context_from_config_custom(mock_git_commands, mock_git_interface):
    """Test creating GlobalContext from a populated GlobalConfig."""
    # Execute
    config = GlobalConfig(
        model="anthropic:claude-3",
        api_key="sk-ant",
        temperature=0.2,
        aggresiveness="Conservative",
        verbose=True,
        auto_accept=True,
    )
    repo_path = Path("/tmp/repo")
    context = GlobalContext.from_global_config(config, repo_path)

    # Verify
    assert context.model is not None
    assert context.verbose is True
    assert context.temperature == 0.2
    assert context.aggresiveness == "Conservative"
    assert context.auto_accept is True


def test_fix_context():
    ctx = FixContext(commit_hash="abc1234")
    assert ctx.commit_hash == "abc1234"


def test_clean_context_defaults():
    ctx = CleanContext()
    assert ctx.ignore is None
    assert ctx.min_size is None
    assert ctx.start_from is None
    assert ctx.skip_merge is False
