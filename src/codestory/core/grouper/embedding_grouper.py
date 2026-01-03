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
from typing import Literal

from tqdm import tqdm

from codestory.core.data.chunk import Chunk
from codestory.core.data.commit_group import CommitGroup
from codestory.core.data.immutable_chunk import ImmutableChunk
from codestory.core.diff_generation.semantic_diff_generator import SemanticDiffGenerator
from codestory.core.embeddings.clusterer import Clusterer
from codestory.core.embeddings.embedder import Embedder
from codestory.core.grouper.interface import LogicalGrouper
from codestory.core.llm import CodeStoryAdapter
from codestory.core.semantic_grouper.context_manager import ContextManager
from codestory.summarization.chunk_summarizer import ChunkSummarizer


@dataclass
class Cluster:
    chunks: list[Chunk | ImmutableChunk]
    summaries: list[str]


class EmbeddingGrouper(LogicalGrouper):
    """
    Groups code chunks into logical commit groups using embedding-based clustering.

    This grouper:
    1. Generates summaries for each chunk using ChunkSummarizer
    2. Embeds the summaries using an embedding model
    3. Clusters similar summaries together
    4. Generates combined commit messages for each cluster
    """

    def __init__(
        self,
        model: CodeStoryAdapter,
        batching_strategy: Literal["auto", "requests", "prompt"] = "auto",
        max_tokens: int = 4096,
        custom_embedding_model: str | None = None,
        cluster_strictness: float = 0.5,
        embedder: Embedder | None = None,
    ):
        self.model = model
        self.batching_strategy = batching_strategy
        self.embedder = embedder or Embedder(custom_embedding_model)
        self.clusterer = Clusterer(cluster_strictness)
        self.patch_cutoff_chars = 1000
        self.max_tokens = max_tokens

        # Initialize chunk summarizer for generating summaries
        self._chunk_summarizer = ChunkSummarizer(
            codestory_adapter=model,
            batching_strategy=batching_strategy,
            max_tokens=max_tokens,
            patch_cutoff_chars=self.patch_cutoff_chars,
        )

    def group_chunks(
        self,
        chunks: list[Chunk],
        immut_chunks: list[ImmutableChunk],
        context_manager: ContextManager,
        message: str,
        pbar: tqdm | None = None,
    ) -> list[CommitGroup]:
        """
        Group chunks into logical commit groups using embedding-based clustering.

        Args:
            chunks: List of regular Chunk objects
            immut_chunks: List of ImmutableChunk objects (binary files, etc.)
            context_manager: ContextManager for semantic analysis
            message: Optional user-provided intent message
            pbar: Optional progress bar

        Returns:
            List of CommitGroup objects, each containing related chunks and a commit message
        """
        from loguru import logger

        if not (chunks or immut_chunks):
            return []

        # Create diff generator for patch generation
        diff_generator = SemanticDiffGenerator(chunks, context_manager=context_manager)

        # Combine all chunks for summarization
        all_chunks: list[Chunk | ImmutableChunk] = list(chunks) + list(immut_chunks)

        # Step 1: Generate summaries for each chunk
        summaries = self._chunk_summarizer.summarize_chunks(
            chunks=all_chunks,
            context_manager=context_manager,
            diff_generator=diff_generator,
            intent_message=message,
            pbar=pbar,
        )

        # Step 2: Handle single chunk case (no clustering needed)
        if len(all_chunks) == 1:
            return [
                CommitGroup(
                    chunks=[all_chunks[0]],
                    commit_message=summaries[0],
                )
            ]

        # Step 3: Embed summaries and cluster them
        embeddings = self.embedder.embed(summaries)
        cluster_labels = self.clusterer.cluster(embeddings)

        groups = []
        clusters: dict[int, Cluster] = {}

        # Step 4: Build clusters - group chunks and their summaries by cluster label
        for any_chunk, summary, cluster_label in zip(
            all_chunks, summaries, cluster_labels, strict=True
        ):
            if cluster_label == -1:
                # Noise: assign as its own group, reuse summary as commit message
                group = CommitGroup(
                    chunks=[any_chunk],
                    commit_message=summary,
                )
                groups.append(group)
            else:
                if cluster_label not in clusters:
                    clusters[cluster_label] = Cluster(chunks=[], summaries=[])
                clusters[cluster_label].chunks.append(any_chunk)
                clusters[cluster_label].summaries.append(summary)

        # Step 5: Generate combined commit messages for each cluster
        if clusters:
            cluster_messages_map = self._chunk_summarizer.summarize_clusters(
                clusters={cid: cluster.summaries for cid, cluster in clusters.items()},
                intent_message=message,
                pbar=pbar,
            )

            # Create commit groups from clusters
            for cluster_id, cluster in clusters.items():
                commit_message = cluster_messages_map[cluster_id]
                group = CommitGroup(
                    chunks=cluster.chunks,
                    commit_message=commit_message,
                )
                groups.append(group)

        logger.debug(
            f"Organized {len(chunks) + len(immut_chunks)} changes into {len(groups)} logical groups."
        )

        return groups
