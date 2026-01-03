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
import numpy as np
from loguru import logger


class SklearnLouvainClusterer:
    """
    Clusters embeddings using scikit-learn NearestNeighbors + NetworkX Louvain community detection.

    Suitable for small to medium datasets (<1000 embeddings).
    """

    def __init__(
        self,
        min_k: int = 5,
        max_k: int = 50,
        k_factor: float = 0.10,
        resolution: float = 1.5,
    ):
        self.min_k = min_k
        self.max_k = max_k
        self.k_factor = k_factor
        self.resolution = resolution
        self.labels_ = np.array([])

    def fit(self, embeddings: list[list[float]]) -> np.ndarray:
        import networkx as nx
        from sklearn.neighbors import NearestNeighbors
        from sklearn.preprocessing import normalize

        # Early exits for edge cases
        if embeddings is None or len(embeddings) == 0:
            return np.array([])

        embeddings = np.asarray(embeddings, dtype="float32")
        n_samples = embeddings.shape[0]

        if n_samples == 1:
            return np.array([0])

        # Normalize embeddings for cosine similarity
        embeddings = normalize(embeddings, norm="l2")

        # Determine k for nearest neighbors
        k = int(self.k_factor * n_samples)
        k = max(self.min_k, min(self.max_k, int(k)))
        k_search = min(k + 1, n_samples)  # include self (+1)

        # Use brute-force kNN with cosine similarity (via inner product on normalized vectors)
        nbrs = NearestNeighbors(
            n_neighbors=k_search, algorithm="brute", metric="cosine"
        )
        nbrs.fit(embeddings)
        distances, neighbors = nbrs.kneighbors(embeddings)

        # Build weighted similarity graph
        # Convert cosine distances to similarities (similarity = 1 - distance)
        G = nx.Graph()
        G.add_nodes_from(range(n_samples))

        for i in range(n_samples):
            for j_idx in range(1, k_search):  # skip self (0)
                neighbor = neighbors[i, j_idx]
                # Convert distance to similarity for graph weighting
                similarity = 1.0 - distances[i, j_idx]
                if neighbor != -1:
                    G.add_edge(i, neighbor, weight=float(similarity))

        # Louvain community detection
        try:
            communities = nx.community.louvain_communities(
                G, resolution=self.resolution
            )
        except Exception as e:
            logger.warning(
                f"Louvain clustering failed: {e}. Fallback to single cluster."
            )
            return np.zeros(n_samples, dtype=int)

        # Assign cluster labels
        labels = np.full(n_samples, -1, dtype=int)
        for label_id, community in enumerate(communities):
            for node in community:
                labels[node] = label_id

        logger.debug(
            f"Clustered {n_samples} embeddings into {len(communities)} clusters."
        )
        return labels


class Clusterer:
    """
    Wrapper class for clustering embeddings.
    """

    def __init__(self):
        self.clusterer = SklearnLouvainClusterer()

    def cluster(self, embeddings: list[list[float]]):
        return self.clusterer.fit(embeddings)
