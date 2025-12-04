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

from codestory.core.file_reader.git_file_reader import GitFileReader
from codestory.core.git_interface.interface import GitInterface

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


def test_read_new_content():
    mock_git = Mock(spec=GitInterface)
    mock_git.run_git_text_out.return_value = "content"

    reader = GitFileReader(mock_git, "base", "head")
    content = reader.read("path/to/file.txt", old_content=False)

    assert content == "content"
    mock_git.run_git_text_out.assert_called_once_with(
        ["cat-file", "-p", "head:path/to/file.txt"]
    )


def test_read_old_content():
    mock_git = Mock(spec=GitInterface)
    mock_git.run_git_text_out.return_value = "old content"

    reader = GitFileReader(mock_git, "base", "head")
    content = reader.read("path/to/file.txt", old_content=True)

    assert content == "old content"
    mock_git.run_git_text_out.assert_called_once_with(
        ["cat-file", "-p", "base:path/to/file.txt"]
    )


def test_read_path_normalization():
    mock_git = Mock(spec=GitInterface)

    reader = GitFileReader(mock_git, "base", "head")
    reader.read("path\\to\\file.txt")

    mock_git.run_git_text_out.assert_called_once_with(
        ["cat-file", "-p", "head:path/to/file.txt"]
    )


def test_read_returns_none_on_failure():
    mock_git = Mock(spec=GitInterface)
    mock_git.run_git_text_out.return_value = None

    reader = GitFileReader(mock_git, "base", "head")
    content = reader.read("nonexistent.txt")

    assert content is None
