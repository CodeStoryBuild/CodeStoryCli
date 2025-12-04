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

from codestory.core.data.chunk import Chunk
from codestory.core.data.composite_diff_chunk import CompositeDiffChunk

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


def test_init_empty_raises():
    with pytest.raises(RuntimeError, match="Chunks must be a nonempty list"):
        CompositeDiffChunk([])


def test_canonical_paths():
    c1 = Mock(spec=Chunk)
    c1.canonical_paths.return_value = [b"a.txt"]

    c2 = Mock(spec=Chunk)
    c2.canonical_paths.return_value = [b"b.txt"]

    c3 = Mock(spec=Chunk)
    c3.canonical_paths.return_value = [b"a.txt"]  # Duplicate path

    composite = CompositeDiffChunk([c1, c2, c3])

    paths = composite.canonical_paths()
    assert len(paths) == 2
    assert set(paths) == {b"a.txt", b"b.txt"}


def test_hunk_ranges():
    c1 = Mock()
    c1.hunk_ranges.return_value = {b"a.txt": [(1, 1, 1, 1)]}

    c2 = Mock()
    c2.hunk_ranges.return_value = {b"b.txt": [(2, 2, 2, 2)]}

    c3 = Mock()
    c3.hunk_ranges.return_value = {b"a.txt": [(3, 3, 3, 3)]}

    composite = CompositeDiffChunk([c1, c2, c3])

    ranges = composite.hunk_ranges()
    assert len(ranges) == 2
    assert len(ranges[b"a.txt"]) == 2
    assert (1, 1, 1, 1) in ranges[b"a.txt"]
    assert (3, 3, 3, 3) in ranges[b"a.txt"]
    assert ranges[b"b.txt"] == [(2, 2, 2, 2)]


def test_get_chunks_flattening():
    # c1 is a leaf chunk
    c1 = Mock(spec=Chunk)
    c1.get_chunks.return_value = [c1]

    # c2 is a leaf chunk
    c2 = Mock(spec=Chunk)
    c2.get_chunks.return_value = [c2]

    # composite contains c1 and c2
    composite = CompositeDiffChunk([c1, c2])

    flattened = composite.get_chunks()
    assert len(flattened) == 2
    assert flattened[0] is c1
    assert flattened[1] is c2

    # Nested composite
    composite_nested = CompositeDiffChunk([composite, c1])
    # composite.get_chunks() returns [c1, c2]
    # c1.get_chunks() returns [c1]
    # So composite_nested.get_chunks() should return [c1, c2, c1]

    flattened_nested = composite_nested.get_chunks()
    assert len(flattened_nested) == 3
    assert flattened_nested[0] is c1
    assert flattened_nested[1] is c2
    assert flattened_nested[2] is c1
