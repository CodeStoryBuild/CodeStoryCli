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

from codestory.core.diff.data.atomic_container import AtomicContainer
from codestory.core.diff.data.composite_container import CompositeContainer

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


def test_canonical_paths():
    c1 = Mock(spec=AtomicContainer)
    c1.canonical_paths.return_value = ["a.txt"]

    c2 = Mock(spec=AtomicContainer)
    c2.canonical_paths.return_value = ["b.txt"]

    c3 = Mock(spec=AtomicContainer)
    c3.canonical_paths.return_value = ["a.txt"]  # Duplicate path

    composite = CompositeContainer([c1, c2, c3])

    paths = composite.canonical_paths()
    assert len(paths) == 2
    assert set(paths) == {"a.txt", "b.txt"}


def test_get_atomic_chunks_flattening():
    # c1 is a leaf container
    c1 = Mock(spec=AtomicContainer)
    c1.get_atomic_chunks.return_value = [Mock()]

    # c2 is a leaf container
    c2 = Mock(spec=AtomicContainer)
    c2.get_atomic_chunks.return_value = [Mock()]

    # composite contains c1 and c2
    composite = CompositeContainer([c1, c2])

    flattened = composite.get_atomic_chunks()
    assert len(flattened) == 2
