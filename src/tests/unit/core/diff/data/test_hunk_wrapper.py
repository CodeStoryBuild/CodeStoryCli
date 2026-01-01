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

from codestory.core.diff.creation.hunk_wrapper import HunkWrapper

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


def test_init_and_properties():
    hunk = HunkWrapper(
        new_file_path=b"new.txt",
        old_file_path=b"old.txt",
        hunk_lines=[b"line1"],
        old_start=1,
        new_start=1,
        old_len=1,
        new_len=1,
    )

    assert hunk.new_file_path == b"new.txt"
    assert hunk.old_file_path == b"old.txt"
    assert hunk.file_path == b"new.txt"
    assert hunk.file_mode == b"100644"  # Default


def test_create_empty_content():
    hunk = HunkWrapper.create_empty_content(
        new_file_path=b"new.txt", old_file_path=b"old.txt", file_mode=b"100755"
    )

    assert hunk.new_file_path == b"new.txt"
    assert hunk.old_file_path == b"old.txt"
    assert hunk.hunk_lines == []
    assert hunk.old_start == 0
    assert hunk.new_start == 0
    assert hunk.old_len == 0
    assert hunk.new_len == 0
    assert hunk.file_mode == b"100755"


def test_create_empty_addition():
    hunk = HunkWrapper.create_empty_addition(new_file_path=b"new.txt")

    assert hunk.new_file_path == b"new.txt"
    assert hunk.old_file_path is None
    assert hunk.hunk_lines == []


def test_create_empty_deletion():
    hunk = HunkWrapper.create_empty_deletion(old_file_path=b"old.txt")

    assert hunk.new_file_path is None
    assert hunk.old_file_path == b"old.txt"
    assert hunk.hunk_lines == []
