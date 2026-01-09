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

from unittest.mock import Mock, patch

import pytest

from codestory.core.exceptions import (
    DetachedHeadError,
    GitError,
    ValidationError,
)
from codestory.core.git.git_commands import GitCommands
from codestory.core.validation import (
    sanitize_user_input,
    validate_commit_hash,
    validate_default_branch,
    validate_git_repository,
    validate_ignore_patterns,
    validate_message_length,
    validate_min_size,
    validate_target_path,
)

# -----------------------------------------------------------------------------
# sanitize_user_input
# -----------------------------------------------------------------------------


def test_sanitize_user_input_valid():
    assert sanitize_user_input("valid input") == "valid input"
    assert sanitize_user_input("  trimmed  ") == "trimmed"


def test_sanitize_user_input_clipping():
    long_input = "a" * 2000
    with pytest.raises(ValidationError, match="Input too long"):
        sanitize_user_input(long_input, max_length=1000)


def test_sanitize_user_input_sanitization():
    # Null bytes and control characters should be removed
    dirty_input = "hello\x00world\x1b[31m"
    # Note: The implementation keeps printable, newline, and tab.
    # \x1b is escape, not printable. \x00 is null.
    # Expect "helloworld[31m" because [31m are printable chars.
    assert sanitize_user_input(dirty_input) == "helloworld[31m"

    # Newlines and tabs are allowed
    assert sanitize_user_input("line1\nline2\tcol") == "line1\nline2\tcol"


def test_sanitize_user_input_type_error():
    with pytest.raises(ValidationError, match="Input must be a string"):
        sanitize_user_input(123)
    with pytest.raises(ValidationError, match="Input must be a string"):
        sanitize_user_input(None)


# -----------------------------------------------------------------------------
# validate_git_repository
# -----------------------------------------------------------------------------


@pytest.fixture
def mock_git_commands():
    return Mock(spec=GitCommands)


def test_validate_git_repository_success(mock_git_commands):
    # Setup mock to return success for is_git_repo
    mock_git_commands.is_git_repo.return_value = True
    mock_git_commands.get_repo_root.return_value = "/fake"

    # Should not raise
    with patch("os.getcwd", return_value="/fake"):
        validate_git_repository(mock_git_commands)


def test_validate_git_repository_not_in_repo(mock_git_commands):
    mock_git_commands.is_git_repo.return_value = False

    with pytest.raises(GitError, match="Not a git repository"):
        validate_git_repository(mock_git_commands)


# -----------------------------------------------------------------------------
# validate_default_branch
# -----------------------------------------------------------------------------


def test_validate_default_branch_success(mock_git_commands):
    mock_git_commands.get_show_current_branch.return_value = "main"

    # Should not raise
    validate_default_branch(mock_git_commands)


def test_validate_default_branch_detached_head(mock_git_commands):
    mock_git_commands.get_show_current_branch.return_value = (
        ""  # Empty string indicates detached HEAD
    )

    with pytest.raises(DetachedHeadError, match="detached HEAD"):
        validate_default_branch(mock_git_commands)


def test_validate_default_branch_failed_check(mock_git_commands):
    mock_git_commands.get_show_current_branch.return_value = None

    with pytest.raises(GitError, match="detached HEAD"):
        validate_default_branch(mock_git_commands)


# -----------------------------------------------------------------------------
# validate_commit_hash
# -----------------------------------------------------------------------------


def test_validate_commit_hash_valid():
    assert validate_commit_hash("a1b2c3d4") == "a1b2c3d4"
    assert validate_commit_hash("A1B2C3D4") == "a1b2c3d4"  # Normalization


def test_validate_commit_hash_head_resolution(mock_git_commands):
    mock_git_commands.get_commit_hash.return_value = "a1b2c3d4"
    assert (
        validate_commit_hash("HEAD", git_commands=mock_git_commands, branch="main")
        == "a1b2c3d4"
    )
    mock_git_commands.get_commit_hash.assert_called_with("main")


def test_validate_commit_hash_invalid_format():
    with pytest.raises(ValidationError, match="Invalid commit hash format"):
        validate_commit_hash("not-a-hash")
    with pytest.raises(ValidationError, match="Invalid commit hash format"):
        validate_commit_hash("123")  # Too short


def test_validate_commit_hash_type_error():
    with pytest.raises(ValidationError, match="Commit hash cannot be empty"):
        validate_commit_hash(None)
    with pytest.raises(ValidationError, match="Commit hash cannot be empty"):
        validate_commit_hash(123)


# -----------------------------------------------------------------------------
# validate_target_path
# -----------------------------------------------------------------------------


def test_validate_target_path_valid_file(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("content")
    assert validate_target_path(str(f)) == [str(f)]


def test_validate_target_path_valid_dir(tmp_path):
    d = tmp_path / "subdir"
    d.mkdir()
    assert validate_target_path(str(d)) == [str(d)]


def test_validate_target_path_none():
    assert validate_target_path(None) is None


def test_validate_target_path_list():
    assert validate_target_path(["path1", "path2"]) == ["path1", "path2"]


def test_validate_target_path_type_error():
    with pytest.raises(ValidationError, match="Target path cannot be empty"):
        validate_target_path("")
    with pytest.raises(
        ValidationError, match="Target path must be a string or a list of strings"
    ):
        validate_target_path(123)


# -----------------------------------------------------------------------------
# validate_message_length
# -----------------------------------------------------------------------------


def test_validate_message_length_valid():
    assert validate_message_length("valid message") == "valid message"
    assert validate_message_length(None) is None


def test_validate_message_length_too_long():
    long_msg = "a" * 1001
    with pytest.raises(ValidationError, match="Commit message is too long"):
        validate_message_length(long_msg)


def test_validate_message_length_empty():
    with pytest.raises(ValidationError, match="Commit message cannot be empty"):
        validate_message_length("")
    with pytest.raises(ValidationError, match="Commit message cannot be empty"):
        validate_message_length("   ")


def test_validate_message_length_null_bytes():
    with pytest.raises(ValidationError, match="contains null bytes"):
        validate_message_length("hello\x00world")


def test_validate_message_length_type_error():
    with pytest.raises(ValidationError, match="Commit message must be a string"):
        validate_message_length(123)


# -----------------------------------------------------------------------------
# validate_ignore_patterns
# -----------------------------------------------------------------------------


def test_validate_ignore_patterns_valid():
    assert validate_ignore_patterns(["a1b2", "C3D4"]) == ["a1b2", "c3d4"]
    assert validate_ignore_patterns(None) == []


def test_validate_ignore_patterns_invalid_content():
    with pytest.raises(ValidationError, match="Invalid ignore pattern"):
        validate_ignore_patterns(["not-hex"])


def test_validate_ignore_patterns_type_error():
    with pytest.raises(ValidationError, match="Ignore patterns must be a list"):
        validate_ignore_patterns("not-a-list")
    with pytest.raises(ValidationError, match="must be a string"):
        validate_ignore_patterns([123])


# -----------------------------------------------------------------------------
# validate_min_size
# -----------------------------------------------------------------------------


def test_validate_min_size_valid():
    assert validate_min_size(10) == 10
    assert validate_min_size(None) is None


def test_validate_min_size_bounds():
    with pytest.raises(ValidationError, match="must be positive"):
        validate_min_size(0)
    with pytest.raises(ValidationError, match="too large"):
        validate_min_size(10001)


def test_validate_min_size_type_error():
    with pytest.raises(ValidationError, match="must be an integer"):
        validate_min_size("10")
