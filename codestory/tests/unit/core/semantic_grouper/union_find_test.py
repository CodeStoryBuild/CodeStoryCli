# -----------------------------------------------------------------------------
# dslate - Dual Licensed Software
# Copyright (c) 2025 Adem Can
#
# This file is part of DSLATE.
#
# DSLATE is available under a dual-license:
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
from codestory.core.semantic_grouper.union_find import UnionFind

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
