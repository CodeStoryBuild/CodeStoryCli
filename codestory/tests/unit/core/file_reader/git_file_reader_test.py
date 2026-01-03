# -----------------------------------------------------------------------------
# codestory - Dual Licensed Software
# Copyright (c) 2025 Adem Can
#
# This file is part of codestory.
#
# codestory is available under a dual-license:
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
