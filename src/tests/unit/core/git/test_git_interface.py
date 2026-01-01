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
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from codestory.core.git.git_interface import GitInterface

# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def git_interface():
    return GitInterface(repo_path="/tmp/repo")


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


def test_init_path_conversion():
    """Test that string path is converted to Path object."""
    gi = GitInterface("/tmp/string_path")
    assert isinstance(gi.repo_path, Path)
    assert str(gi.repo_path) == str(Path("/tmp/string_path"))

    gi2 = GitInterface(Path("/tmp/path_obj"))
    assert isinstance(gi2.repo_path, Path)


@patch("subprocess.run")
def test_run_git_text_success(mock_run, git_interface):
    """Test successful text command execution."""
    # Setup mock
    mock_result = Mock(spec=subprocess.CompletedProcess)
    mock_result.returncode = 0
    mock_result.stdout = "output"
    mock_result.stderr = ""
    mock_run.return_value = mock_result

    # Execute
    result = git_interface.run_git_text(["status"])

    # Verify
    assert result == mock_result
    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args

    # Check arguments passed to subprocess.run
    assert args[0] == ["git", "status"]
    assert kwargs["text"] is True
    assert kwargs["encoding"] == "utf-8"
    assert kwargs["cwd"] == str(git_interface.repo_path)


@patch("subprocess.run")
def test_run_git_text_cwd_override(mock_run, git_interface):
    """Test that cwd argument overrides default repo path."""
    mock_run.return_value = Mock(
        spec=subprocess.CompletedProcess, returncode=0, stdout="", stderr=""
    )

    git_interface.run_git_text(["status"], cwd="/custom/cwd")

    _, kwargs = mock_run.call_args
    assert kwargs["cwd"] == "/custom/cwd"


@patch("subprocess.run")
def test_run_git_text_failure(mock_run, git_interface):
    """Test handling of CalledProcessError."""
    # Setup mock to raise exception
    error = subprocess.CalledProcessError(1, ["git", "fail"], stderr="error msg")
    mock_run.side_effect = error

    # Execute
    result = git_interface.run_git_text(["fail"])

    # Verify
    assert result is None


@patch("subprocess.run")
def test_run_git_binary_success(mock_run, git_interface):
    """Test successful binary command execution."""
    # Setup mock
    mock_result = Mock(spec=subprocess.CompletedProcess)
    mock_result.returncode = 0
    mock_result.stdout = b"binary\x00data"
    mock_result.stderr = b""
    mock_run.return_value = mock_result

    # Execute
    result = git_interface.run_git_binary(["cat-file", "-p", "HEAD"])

    # Verify
    assert result == mock_result
    _, kwargs = mock_run.call_args
    assert kwargs["text"] is False
    assert kwargs["encoding"] is None


@patch("subprocess.run")
def test_run_git_binary_failure(mock_run, git_interface):
    """Test handling of CalledProcessError in binary mode."""
    error = subprocess.CalledProcessError(1, ["git", "fail"], stderr=b"error")
    mock_run.side_effect = error

    result = git_interface.run_git_binary(["fail"])
    assert result is None


def test_run_git_text_out_wrapper(git_interface):
    """Test the convenience wrapper for text output."""
    # Mock the internal run_git_text method
    with patch.object(git_interface, "run_git_text") as mock_run:
        mock_result = Mock(spec=subprocess.CompletedProcess)
        mock_result.stdout = "success"
        mock_run.return_value = mock_result

        output = git_interface.run_git_text_out(["status"])
        assert output == "success"

        # Test None return on error
        mock_run.return_value = None
        output = git_interface.run_git_text_out(["fail"])
        assert output is None


def test_run_git_binary_out_wrapper(git_interface):
    """Test the convenience wrapper for binary output."""
    with patch.object(git_interface, "run_git_binary") as mock_run:
        mock_result = Mock(spec=subprocess.CompletedProcess)
        mock_result.stdout = b"bytes"
        mock_run.return_value = mock_result

        output = git_interface.run_git_binary_out(["cat"])
        assert output == b"bytes"

        mock_run.return_value = None
        output = git_interface.run_git_binary_out(["fail"])
        assert output is None
