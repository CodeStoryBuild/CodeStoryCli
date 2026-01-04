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

# -----------------------------------------------------------------------------
# codestory - Dual Licensed Software
# Copyright (c) 2025 Adem Can
# -----------------------------------------------------------------------------

from dataclasses import dataclass

from codestory.core.diff.data.atomic_container import AtomicContainer
from codestory.core.diff.data.commit_group import CommitGroup
from codestory.core.diff.data.composite_container import CompositeContainer
from codestory.core.diff.pipeline.grouper import Grouper
from codestory.core.embeddings.clusterer import Clusterer
from codestory.core.embeddings.embedder import Embedder
from codestory.core.semantic_analysis.summarization.chunk_summarizer import (
    ContainerSummarizer,
)


@dataclass
class Cluster:
    """A cluster of related chunks and their summaries."""

    containers: list[AtomicContainer]
    summaries: list[str]


class EmbeddingGrouper(Grouper):
    """Groups code chunks into logical commit groups using embedding-based clustering.

    This grouper:
    1. Generates summaries for each chunk using ChunkSummarizer
    2. Embeds the summaries using an embedding model
    3. Clusters similar summaries together
    4. Generates combined commit messages for each cluster
    """

    def __init__(
        self,
        summarizer: ContainerSummarizer,
        embedder: Embedder,
        clusterer: Clusterer,
        user_message: str | None = None,
    ):
        self.embedder = embedder
        self.chunk_summarizer = summarizer
        self.clusterer = clusterer

        self.user_message = user_message

    def group(
        self,
        containers: list[AtomicContainer],
    ) -> list[CommitGroup]:
        """Group chunks into logical commit groups using embedding-based clustering.

        Args:
            chunks: List of regular Chunk objects
            immut_chunks: List of ImmutableDiffChunk objects (binary files, etc.)
            context_manager: ContextManager for semantic analysis
            message: Optional user-provided intent message

        Returns:
            List of CommitGroup objects, each containing related chunks and a commit message
        """
        from loguru import logger

        if not containers:
            return []

        summaries = self.chunk_summarizer.summarize_containers(
            containers, user_message=self.user_message, output_style="descriptive"
        )

        # Step 2: Handle single chunk case (no clustering needed)
        # NOTE: summaries length matches containers length
        if len(summaries) == 1:
            # We have a descriptive summary, we need a commit message.
            cluster_msg = self.chunk_summarizer.summarize_clusters(
                clusters={0: [summaries[0]]},
                user_message=self.user_message,
                source_style="descriptive",
            )[0]
            return [CommitGroup(container=containers[0], commit_message=cluster_msg)]

        # Step 3: Embed summaries and cluster them
        embeddings = self.embedder.embed(summaries)
        cluster_labels = self.clusterer.cluster(embeddings)

        groups: list[CommitGroup] = []
        clusters: dict[int, Cluster] = {}
        next_noise_id = -1

        # Step 4: Build clusters - group chunks and their summaries by cluster label
        for container, summary, cluster_label in zip(
            containers, summaries, cluster_labels, strict=True
        ):
            target_label = cluster_label
            if target_label == -1:
                # Assign unique ID for noise
                target_label = next_noise_id
                next_noise_id -= 1

            if target_label not in clusters:
                clusters[target_label] = Cluster(containers=[], summaries=[])

            clusters[target_label].containers.append(container)
            clusters[target_label].summaries.append(summary)

        # Step 5: Generate combined commit messages for each cluster
        if clusters:
            cluster_messages_map = self.chunk_summarizer.summarize_clusters(
                clusters={cid: cluster.summaries for cid, cluster in clusters.items()},
                user_message=self.user_message,
                source_style="descriptive",
            )

            # Create commit groups from clusters
            for cluster_id, cluster in clusters.items():
                commit_message = cluster_messages_map[cluster_id]
                # If it was a noise cluster (single item), maintain the original container type if simpler
                if len(cluster.containers) == 1:
                    container_to_use = cluster.containers[0]
                else:
                    container_to_use = CompositeContainer(cluster.containers)

                group = CommitGroup(
                    container=container_to_use,
                    commit_message=commit_message,
                )
                groups.append(group)

        logger.debug(
            f"Organized {len(containers)} changes into {len(groups)} logical groups."
        )

        return groups
