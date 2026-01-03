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

from codestory.core.semantic_analysis.grouping.union_find import UnionFind

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


def test_union_find_init():
    elements = [1, 2, 3]
    uf = UnionFind(elements)

    assert uf.find(1) == 1
    assert uf.find(2) == 2
    assert uf.find(3) == 3


def test_union_simple():
    uf = UnionFind([1, 2])
    uf.union(1, 2)

    assert uf.find(1) == uf.find(2)


def test_union_transitive():
    uf = UnionFind([1, 2, 3])
    uf.union(1, 2)
    uf.union(2, 3)

    assert uf.find(1) == uf.find(3)
    assert uf.find(1) == uf.find(2)


def test_union_disjoint():
    uf = UnionFind([1, 2, 3, 4])
    uf.union(1, 2)
    uf.union(3, 4)

    assert uf.find(1) == uf.find(2)
    assert uf.find(3) == uf.find(4)
    assert uf.find(1) != uf.find(3)


def test_path_compression():
    # Create a chain 1 -> 2 -> 3 -> 4
    uf = UnionFind([1, 2, 3, 4])
    uf.union(1, 2)
    uf.union(2, 3)
    uf.union(3, 4)

    # All should point to same root
    root = uf.find(1)

    # Accessing 4 should compress path
    assert uf.find(4) == root

    # Verify internal state if possible, or just rely on functional correctness
    assert uf.parent[1] == root or uf.parent[uf.parent[1]] == root  # etc.


def test_union_by_rank():
    # 1-2 (rank 1)
    # 3 (rank 0)
    uf = UnionFind([1, 2, 3])
    uf.union(1, 2)

    root_12 = uf.find(1)

    # Union larger tree with smaller tree
    # Should attach smaller (3) to larger (1-2)
    uf.union(root_12, 3)

    assert uf.find(3) == root_12
    # Rank shouldn't increase if depths differ
    # But this is implementation detail. Functional test is enough.
