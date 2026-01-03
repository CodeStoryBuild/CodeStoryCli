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


import pytest
from codestory.core.data.hunk_wrapper import HunkWrapper

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
