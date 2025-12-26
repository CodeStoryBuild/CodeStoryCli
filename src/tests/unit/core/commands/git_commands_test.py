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

from codestory.core.data.diff_chunk import DiffChunk
from codestory.core.data.hunk_wrapper import HunkWrapper
from codestory.core.data.immutable_hunk_wrapper import ImmutableHunkWrapper
from codestory.core.git_commands.git_commands import GitCommands

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
# Regex Tests
# -----------------------------------------------------------------------------


def test_regex_patterns(git_commands):
    """Test that regex patterns match expected git output formats."""
    # Mode
    assert git_commands._MODE_RE.match(b"new file mode 100644")
    assert git_commands._MODE_RE.match(b"deleted file mode 100644")

    # Index
    assert git_commands._INDEX_RE.match(b"index 0000000..e69de29")
    assert git_commands._INDEX_RE.match(b"index 0000000..e69de29 100644")

    # Paths
    assert git_commands._OLD_PATH_RE.match(b"--- a/file.txt")
    assert git_commands._OLD_PATH_RE.match(b"--- /dev/null")
    assert git_commands._NEW_PATH_RE.match(b"+++ b/file.txt")
    assert git_commands._NEW_PATH_RE.match(b"+++ /dev/null")

    # A/B Paths fallback
    m = git_commands._A_B_PATHS_RE.match(b"diff --git a/foo.py b/bar.py")
    assert m.group(1) == b"foo.py"
    assert m.group(2) == b"bar.py"


# -----------------------------------------------------------------------------
# Parse File Metadata Tests
# -----------------------------------------------------------------------------


def test_parse_file_metadata_standard(git_commands):
    lines = [
        b"diff --git a/test.txt b/test.txt",
        b"index 123..456 100644",
        b"--- a/test.txt",
        b"+++ b/test.txt",
    ]
    old, new, mode = git_commands._parse_file_metadata(lines)
    assert old == b"test.txt"
    assert new == b"test.txt"
    assert mode is None


def test_parse_file_metadata_new_file(git_commands):
    lines = [
        b"diff --git a/new.txt b/new.txt",
        b"new file mode 100644",
        b"index 000..123",
        b"--- /dev/null",
        b"+++ b/new.txt",
    ]
    old, new, mode = git_commands._parse_file_metadata(lines)
    assert old is None
    assert new == b"new.txt"
    assert mode == b"100644"


def test_parse_file_metadata_deleted_file(git_commands):
    lines = [
        b"diff --git a/del.txt b/del.txt",
        b"deleted file mode 100644",
        b"index 123..000",
        b"--- a/del.txt",
        b"+++ /dev/null",
    ]
    old, new, mode = git_commands._parse_file_metadata(lines)
    assert old == b"del.txt"
    assert new is None
    assert mode == b"100644"


def test_parse_file_metadata_rename(git_commands):
    lines = [
        b"diff --git a/old.txt b/new.txt",
        b"similarity index 100%",
        b"rename from old.txt",
        b"rename to new.txt",
        b"--- a/old.txt",
        b"+++ b/new.txt",
    ]
    old, new, mode = git_commands._parse_file_metadata(lines)
    assert old == b"old.txt"
    assert new == b"new.txt"


def test_parse_file_metadata_fallback(git_commands):
    """Test fallback parsing when --- and +++ are missing (e.g. empty file addition)."""
    lines = [
        b"diff --git a/empty.txt b/empty.txt",
        b"new file mode 100644",
        b"index 000..123",
    ]
    old, new, mode = git_commands._parse_file_metadata(lines)
    assert old is None
    assert new == b"empty.txt"
    assert mode == b"100644"


# -----------------------------------------------------------------------------
# Get Full Working Diff Tests (Mocked)
# -----------------------------------------------------------------------------


def test_get_full_working_diff_simple(git_commands, mock_git):
    diff_output = (
        b"diff --git a/file.txt b/file.txt\n"
        b"index 111..222 100644\n"
        b"--- a/file.txt\n"
        b"+++ b/file.txt\n"
        b"@@ -1,1 +1,1 @@\n"
        b"-old\n"
        b"+new\n"
    )
    mock_git.run_git_binary_out.return_value = diff_output

    # Mock _get_binary_files to return empty set
    git_commands._get_binary_files = Mock(return_value=set())

    hunks = git_commands.get_full_working_diff("base", "new")

    assert len(hunks) == 1
    assert isinstance(hunks[0], HunkWrapper)
    assert hunks[0].old_file_path == b"file.txt"
    assert hunks[0].hunk_lines == [b"-old", b"+new"]


def test_get_full_working_diff_binary(git_commands, mock_git):
    diff_output = (
        b"diff --git a/bin.dat b/bin.dat\n"
        b"index 111..222 100644\n"
        b"Binary files a/bin.dat and b/bin.dat differ\n"
    )
    mock_git.run_git_binary_out.return_value = diff_output
    git_commands._get_binary_files = Mock(return_value={b"bin.dat"})

    hunks = git_commands.get_full_working_diff("base", "new")

    assert len(hunks) == 1
    assert isinstance(hunks[0], ImmutableHunkWrapper)
    assert hunks[0].canonical_path == b"bin.dat"


# -----------------------------------------------------------------------------
# Merge Overlapping Chunks Tests
# -----------------------------------------------------------------------------


def create_chunk(path, old_start, old_len, new_start, new_len):
    """Helper to create a DiffChunk."""
    lines = []
    # Generate removals for old_len
    for _i in range(old_len):
        lines.append(b"-old line")
    # Generate additions for new_len
    for _i in range(new_len):
        lines.append(b"+new line")

    hunk = HunkWrapper(
        new_file_path=path.encode(),
        old_file_path=path.encode(),
        file_mode=None,
        hunk_lines=lines,
        old_start=old_start,
        new_start=new_start,
        old_len=old_len,
        new_len=new_len,
    )
    return DiffChunk.from_hunk(hunk)


# -----------------------------------------------------------------------------
# Binary Detection Tests
# -----------------------------------------------------------------------------


def test_get_binary_files(git_commands, mock_git):
    # Mock numstat output
    mock_git.run_git_binary_out.return_value = (
        b"-\t-\tbin.dat\n1\t1\ttext.txt\n-\t-\trenamed.bin => new.bin\n"
    )

    binary_files = git_commands._get_binary_files("base", "new")
    assert b"bin.dat" in binary_files
    assert b"text.txt" not in binary_files
    assert b"new.bin" in binary_files


def test_is_binary_or_unparsable(git_commands):
    # Case 1: In binary set
    assert (
        git_commands._is_binary_or_unparsable([], None, b"bin.dat", {b"bin.dat"})
        is True
    )

    # Case 2: Submodule mode
    assert git_commands._is_binary_or_unparsable([], b"160000", b"sub", set()) is True

    # Case 3: Explicit binary line
    assert (
        git_commands._is_binary_or_unparsable(
            [b"Binary files differ"], None, b"file", set()
        )
        is True
    )

    # Case 4: Normal file
    assert (
        git_commands._is_binary_or_unparsable(
            [b"diff content"], b"100644", b"file.txt", set()
        )
        is False
    )
