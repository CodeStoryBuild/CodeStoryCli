import pytest
from unittest.mock import Mock, patch
from pathlib import Path
from dslate.context import (
    GlobalConfig,
    GlobalContext,
    CommitContext,
    FixContext,
    CleanContext,
)

# -----------------------------------------------------------------------------
# GlobalConfig Tests
# -----------------------------------------------------------------------------

def test_global_config_defaults():
    """Test that GlobalConfig has expected default values."""
    config = GlobalConfig()
    assert config.model is None
    assert config.api_key is None
    assert config.model_temperature == 0.7
    assert config.aggresiveness == "Regular"
    assert config.verbose is False
    assert config.auto_accept is False

def test_global_config_custom_values():
    """Test setting custom values in GlobalConfig."""
    config = GlobalConfig(
        model="openai:gpt-4",
        api_key="sk-test",
        model_temperature=0.5,
        aggresiveness="Extra",
        verbose=True,
        auto_accept=True
    )
    assert config.model == "openai:gpt-4"
    assert config.api_key == "sk-test"
    assert config.model_temperature == 0.5
    assert config.aggresiveness == "Extra"
    assert config.verbose is True
    assert config.auto_accept is True

# -----------------------------------------------------------------------------
# GlobalContext Tests
# -----------------------------------------------------------------------------


@patch("dslate.context.try_create_model")
@patch("dslate.context.SubprocessGitInterface")
@patch("dslate.context.GitCommands")
def test_global_context_from_config_defaults(
    mock_git_commands, mock_git_interface, mock_create_model
):
    """Test creating GlobalContext from an empty GlobalConfig (defaults)."""
    # Setup mocks
    mock_model = Mock()
    mock_create_model.return_value = mock_model

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
    assert context.model == mock_model
    assert context.git_interface == mock_interface_instance
    assert context.git_commands == mock_commands_instance
    assert context.verbose is False
    assert context.model_temperature == 0.7
    assert context.aggresiveness == "Regular"
    assert context.auto_accept is False

    # Verify calls
    mock_create_model.assert_called_once_with(None, None, 0.7)
    mock_git_interface.assert_called_once_with(repo_path)
    mock_git_commands.assert_called_once_with(mock_interface_instance)

@patch("dslate.context.try_create_model")
@patch("dslate.context.SubprocessGitInterface")
@patch("dslate.context.GitCommands")
def test_global_context_from_config_custom(
    mock_git_commands, mock_git_interface, mock_create_model
):
    """Test creating GlobalContext from a populated GlobalConfig."""
    # Setup mocks
    mock_model = Mock()
    mock_create_model.return_value = mock_model

    # Execute
    config = GlobalConfig(
        model="claude-3",
        api_key="sk-ant",
        model_temperature=0.2,
        aggresiveness="Conservative",
        verbose=True,
        auto_accept=True,
    )
    repo_path = Path("/tmp/repo")
    context = GlobalContext.from_global_config(config, repo_path)

    # Verify
    assert context.model == mock_model
    assert context.verbose is True
    assert context.model_temperature == 0.2
    assert context.aggresiveness == "Conservative"
    assert context.auto_accept is True

    # Verify calls
    mock_create_model.assert_called_once_with("claude-3", "sk-ant", 0.2)

# -----------------------------------------------------------------------------
# Other Context Tests
# -----------------------------------------------------------------------------

def test_commit_context_defaults():
    ctx = CommitContext()
    assert ctx.target == "."
    assert ctx.message is None

def test_fix_context():
    ctx = FixContext(commit_hash="abc1234")
    assert ctx.commit_hash == "abc1234"

def test_clean_context_defaults():
    ctx = CleanContext()
    assert ctx.ignore is None
    assert ctx.min_size is None
    assert ctx.start_from is None
    assert ctx.skip_merge is False
