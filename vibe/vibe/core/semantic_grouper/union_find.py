class UnionFind:
    """Union-Find (Disjoint Set Union) with path compression and union by rank."""

    def __init__(self, elements):
        self.parent = {el: el for el in elements}
        self.rank = {el: 0 for el in elements}  # Tracks tree depth

    def find(self, i):
        if self.parent[i] != i:
            self.parent[i] = self.find(self.parent[i])  # Path compression
        return self.parent[i]

    def union(self, i, j):
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
