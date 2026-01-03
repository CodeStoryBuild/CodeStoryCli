import hdbscan


class Clusterer:
    def __init__(self, hdbScan: hdbscan.HDBSCAN = None):
        if hdbScan is None:
            # TODO find good balance for hyperparameters
            hdbScan = hdbscan.HDBSCAN(
                min_cluster_size=2, metric="euclidean", cluster_selection_method="eom"
            )

        self.clusterer = hdbScan

    def cluster(self, embeddings: list[list[float]]):
        return self.clusterer.fit(embeddings)
