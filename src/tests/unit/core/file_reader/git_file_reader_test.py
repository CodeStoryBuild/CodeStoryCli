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
from codestory.core.git_commands.git_commands import GitCommands


def test_read_all():
    mock_git = Mock(spec=GitCommands)
    # mock_git.cat_file_batch returns a list of bytes or None
    mock_git.cat_file_batch.return_value = [
        b"old content 1",
        b"old content 2",
        b"new content 1",
        None,  # missing new content
    ]

    reader = GitFileReader(mock_git)
    old_files = ["old1.txt", "old2.txt"]
    new_files = ["new1.txt", "new2.txt"]

    old_contents, new_contents = reader.read_all(
        "old_sha", "new_sha", old_files, new_files
    )

    assert old_contents == ["old content 1", "old content 2"]
    assert new_contents == ["new content 1", None]

    expected_objs = [
        "old_sha:old1.txt",
        "old_sha:old2.txt",
        "new_sha:new1.txt",
        "new_sha:new2.txt",
    ]
    mock_git.cat_file_batch.assert_called_once_with(expected_objs)


def test_read_all_path_normalization():
    mock_git = Mock(spec=GitCommands)
    mock_git.cat_file_batch.return_value = [b"content"]

    reader = GitFileReader(mock_git)
    reader.read_all("old", "new", ["path\\to\\file.txt"], [])

    mock_git.cat_file_batch.assert_called_once_with(["old:path/to/file.txt"])
