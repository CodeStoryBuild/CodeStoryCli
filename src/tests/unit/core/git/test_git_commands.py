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

from unittest.mock import Mock

import pytest

from codestory.core.git.git_commands import GitCommands

# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def mock_git():
    return Mock()


@pytest.fixture
def git_commands(mock_git):
    return GitCommands(mock_git)


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


def test_reset(git_commands, mock_git):
    git_commands.reset()
    mock_git.run_git_text_out.assert_called_with(["reset"])


def test_track_untracked_specific(git_commands, mock_git):
    git_commands.track_untracked("file.txt")
    mock_git.run_git_text_out.assert_called_with(["add", "-N", "file.txt"])


def test_track_untracked_all(git_commands, mock_git):
    mock_git.run_git_text_out.return_value = "file1.txt\nfile2.txt"
    git_commands.track_untracked()
    # First call to ls-files
    assert mock_git.run_git_text_out.call_args_list[0][0][0] == [
        "ls-files",
        "--others",
        "--exclude-standard",
    ]
    # Second call to add -N
    assert mock_git.run_git_text_out.call_args_list[1][0][0] == [
        "add",
        "-N",
        "file1.txt",
        "file2.txt",
    ]


def test_get_commit_hash(git_commands, mock_git):
    mock_git.run_git_text_out.return_value = "abc123456789\n"
    res = git_commands.get_commit_hash("main")
    assert res == "abc123456789"
    mock_git.run_git_text_out.assert_called_with(["rev-parse", "main"])


def test_get_commit_hash_error(git_commands, mock_git):
    mock_git.run_git_text_out.return_value = None
    with pytest.raises(ValueError, match="Could not resolve reference"):
        git_commands.get_commit_hash("invalid")


def test_get_rev_list(git_commands, mock_git):
    mock_git.run_git_text_out.return_value = "hash1\nhash2\n"
    res = git_commands.get_rev_list("HEAD~2..HEAD")
    assert res == ["hash1", "hash2"]
    mock_git.run_git_text_out.assert_called_with(["rev-list", "HEAD~2..HEAD"])


def test_cat_file_batch(git_commands, mock_git):
    # Mocking output for two files and one missing
    # Format: <object> SP <type> SP <size> LF <contents> LF
    output = b"file1 blob 8\ncontent1\nfile2 blob 8\ncontent2\nmissing missing\n"
    mock_git.run_git_binary_out.return_value = output

    objs = [b"file1", b"file2", b"missing"]
    contents = git_commands.cat_file_batch(objs)

    assert len(contents) == 3
    assert contents[0] == b"content1"
    assert contents[1] == b"content2"
    assert contents[2] is None

    mock_git.run_git_binary_out.assert_called_once()
    args, kwargs = mock_git.run_git_binary_out.call_args
    assert args[0] == ["cat-file", "--batch"]
    assert b"file1\nfile2\nmissing\n" in kwargs["input_bytes"]


def test_is_git_repo_true(git_commands, mock_git):
    mock_git.run_git_text_out.return_value = "true\n"
    assert git_commands.is_git_repo() is True


def test_is_git_repo_false(git_commands, mock_git):
    mock_git.run_git_text_out.return_value = "false\n"
    assert git_commands.is_git_repo() is False

    mock_git.run_git_text_out.return_value = None
    assert git_commands.is_git_repo() is False


def test_add(git_commands, mock_git):
    mock_git.run_git_text.return_value = "output"
    assert git_commands.add(["file.txt"]) is True
    mock_git.run_git_text.assert_called_with(["add", "file.txt"], env=None)


def test_apply(git_commands, mock_git):
    mock_git.run_git_binary_out.return_value = b"applied"
    assert git_commands.apply(b"diff data", ["--check"]) is True
    mock_git.run_git_binary_out.assert_called_with(
        ["apply", "--check"], input_bytes=b"diff data", env=None
    )
