from collections.abc import Hashable, Iterable


class UnionFind:
    """Union-Find (Disjoint Set Union) with path compression and union by rank."""

    def __init__(self, elements: Iterable[Hashable]) -> None:
        self.parent = {el: el for el in elements}
        self.rank = dict.fromkeys(elements, 0)  # Tracks tree depth

    def find(self, i: Hashable) -> Hashable:
        if self.parent[i] != i:
            self.parent[i] = self.find(self.parent[i])  # Path compression
        return self.parent[i]

    def union(self, i: Hashable, j: Hashable) -> None:
        root_i = self.find(i)
        root_j = self.find(j)

        if root_i == root_j:
            return  # Already in the same set

        # Union by rank
        if self.rank[root_i] < self.rank[root_j]:
            self.parent[root_i] = root_j
        elif self.rank[root_i] > self.rank[root_j]:
            self.parent[root_j] = root_i
        else:
            self.parent[root_j] = root_i
            self.rank[root_i] += 1
