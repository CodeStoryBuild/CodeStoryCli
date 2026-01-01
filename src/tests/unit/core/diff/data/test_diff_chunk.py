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

from codestory.core.diff.creation.diff_creator import DiffCreator
from codestory.core.diff.creation.hunk_wrapper import HunkWrapper
from codestory.core.diff.data.line_changes import Addition, Removal
from codestory.core.diff.data.standard_diff_chunk import StandardDiffChunk

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def create_chunk(
    old_path=b"file.txt", new_path=b"file.txt", old_start=1, parsed_content=None
):
    return StandardDiffChunk(
        base_hash="test_base",
        new_hash="test_new",
        old_file_path=old_path,
        new_file_path=new_path,
        parsed_content=parsed_content or [],
        old_start=old_start,
    )


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


def test_properties_standard():
    c = create_chunk(old_path=b"a.txt", new_path=b"a.txt")
    assert c.is_standard_modification
    assert not c.is_file_rename
    assert not c.is_file_addition
    assert not c.is_file_deletion
    assert c.canonical_path() == b"a.txt"


def test_properties_rename():
    c = create_chunk(old_path=b"a.txt", new_path=b"b.txt")
    assert not c.is_standard_modification
    assert c.is_file_rename
    assert not c.is_file_addition
    assert not c.is_file_deletion
    assert c.canonical_path() == b"b.txt"


def test_properties_addition():
    c = create_chunk(old_path=None, new_path=b"new.txt")
    assert not c.is_standard_modification
    assert not c.is_file_rename
    assert c.is_file_addition
    assert not c.is_file_deletion
    assert c.canonical_path() == b"new.txt"


def test_properties_deletion():
    c = create_chunk(old_path=b"del.txt", new_path=None)
    assert not c.is_standard_modification
    assert not c.is_file_rename
    assert not c.is_file_addition
    assert c.is_file_deletion
    assert c.canonical_path() == b"del.txt"


def test_lengths_and_content():
    # 1 removal, 2 additions
    content = [Removal(1, 1, b"old"), Addition(2, 1, b"new1"), Addition(2, 2, b"new2")]
    c = create_chunk(parsed_content=content)

    assert c.has_content
    assert c.old_len() == 1
    assert c.new_len() == 2


def test_coordinates():
    # Additions at new lines 10 and 11
    content = [Addition(1, 10, b"line1"), Addition(1, 11, b"line2")]
    c = create_chunk(parsed_content=content, old_start=1)

    assert c.get_abs_new_line_start() == 10
    assert c.get_abs_new_line_end() == 11
    assert c.get_min_abs_line() == 10
    assert c.get_abs_new_line_range() == (10, 11)
    assert c.get_old_line_range() == (1, 0)  # old_len is 0 for pure additions


def test_coordinates_mixed():
    # Removal at old 1, Addition at new 10
    content = [Removal(1, 10, b"old"), Addition(2, 10, b"new")]
    c = create_chunk(parsed_content=content, old_start=1)

    assert c.get_abs_new_line_start() == 10
    assert c.get_abs_new_line_end() == 10
    assert c.get_min_abs_line() == 10
    assert c.get_old_line_range() == (1, 1)  # old_len is 1


def test_is_disjoint():
    # Chunk 1: lines 1-5
    # old_start=1, old_len=5 -> ends at 6
    c1 = create_chunk(
        old_start=1, parsed_content=[Removal(i, i, b"") for i in range(1, 6)]
    )

    # Chunk 2: lines 6-10
    # old_start=6, old_len=5
    c2 = create_chunk(
        old_start=6, parsed_content=[Removal(i, i, b"") for i in range(6, 11)]
    )

    # Chunk 3: lines 3-7 (overlaps c1 and c2)
    c3 = create_chunk(
        old_start=3, parsed_content=[Removal(i, i, b"") for i in range(3, 8)]
    )

    assert c1.is_disjoint_from(
        c2
    )  # 1-6 vs 6-11 (touching is disjoint for application order?)
    # c1: 1 -> 6. c2: 6 -> 11. 6 <= 6 is True. So disjoint.

    assert not c1.is_disjoint_from(c3)  # 1-6 vs 3-8. Overlap.
    assert not c2.is_disjoint_from(c3)  # 6-11 vs 3-8. Overlap.

    # Different files
    c_diff = create_chunk(old_path=b"other.txt")
    assert c1.is_disjoint_from(c_diff)


def test_from_hunk():
    git_mock = Mock()
    diff_creator = DiffCreator(git=git_mock)
    hunk = Mock(spec=HunkWrapper)
    hunk.new_file_path = b"file.txt"
    hunk.old_file_path = b"file.txt"
    hunk.file_mode = b"100644"
    hunk.old_start = 10
    hunk.new_start = 20
    hunk.hunk_lines = [b"-old", b"+new", b"\\ No newline at end of file"]

    c = diff_creator.diff_chunk_from_hunk(
        hunk, base_hash="test_base", new_hash="test_new"
    )

    assert c.old_start == 10
    assert len(c.parsed_content) == 2
    assert isinstance(c.parsed_content[0], Removal)
    assert c.parsed_content[0].content == b"old"
    assert isinstance(c.parsed_content[1], Addition)
    assert c.parsed_content[1].content == b"new"
    assert c.parsed_content[1].newline_marker
