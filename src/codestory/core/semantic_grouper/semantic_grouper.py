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

from typing import Literal

from codestory.core.data.chunk import Chunk
from codestory.core.data.composite_diff_chunk import CompositeDiffChunk
from codestory.core.data.diff_chunk import DiffChunk
from codestory.core.semantic_grouper.chunk_lableler import ChunkLabeler
from codestory.core.semantic_grouper.context_manager import ContextManager
from codestory.core.semantic_grouper.semantic_utils import (
    group_by_overlapping_signatures,
    group_fallback_chunks,
)


class SemanticGrouper:
    """
    Groups chunks semantically based on overlapping symbol signatures.

    The grouper flattens composite chunks into individual DiffChunks, generates
    semantic signatures for each chunk, and groups chunks with overlapping signatures
    using a union-find algorithm. Chunks that cannot be analyzed are placed in
    fallback groups based on the configured strategy.
    """

    def __init__(
        self,
        fallback_grouping_strategy: Literal[
            "all_together",
            "by_file_path",
            "by_file_name",
            "by_file_extension",
            "all_alone",
        ] = "all_together",
    ):
        """
        Initialize the SemanticGrouper with a fallback grouping strategy.

        Args:
            fallback_grouping_strategy: Strategy for grouping chunks that fail annotation.
                - 'all_together': All fallback chunks in one group (default)
                - 'by_file_path': Group by complete file path
                - 'by_file_name': Group by file name only
                - 'by_file_extension': Group by file extension
        """
        self.fallback_grouping_strategy = fallback_grouping_strategy

    def group_chunks(
        self,
        chunks: list[Chunk],
        context_manager: ContextManager,
    ) -> list[CompositeDiffChunk]:
        """
        Group chunks semantically based on overlapping symbol signatures.

        Args:
            chunks: List of chunks to group semantically
            context_manager: Context manager for semantic analysis

        Returns:
            List of semantic groups, with fallback group last if it exists

        Raises:
            ValueError: If chunks list is empty
        """
        if not chunks:
            return []

        # Generate signatures for each chunk
        annotated_chunks = ChunkLabeler.annotate_chunks(chunks, context_manager)

        # Separate chunks that can be analyzed from those that cannot
        analyzable_chunks = []
        fallback_chunks = []

        for annotated_chunk in annotated_chunks:
            if annotated_chunk.signature is not None:
                analyzable_chunks.append(annotated_chunk)
            else:
                fallback_chunks.append(annotated_chunk.chunk)

        # Group analyzable chunks using Union-Find based on overlapping signatures
        semantic_groups = []
        if analyzable_chunks:
            grouped_chunks = group_by_overlapping_signatures(analyzable_chunks)
            semantic_groups.extend(grouped_chunks)

        # Add fallback groups based on the configured strategy
        if fallback_chunks:
            fallback_groups = group_fallback_chunks(
                fallback_chunks, self.fallback_grouping_strategy
            )
            semantic_groups.extend(fallback_groups)

        return semantic_groups

    def _flatten_chunks(self, chunks: list[Chunk]) -> list[DiffChunk]:
        """
        Flatten all chunks into a list of DiffChunks.

        Args:
            chunks: List of chunks (may include composite chunks)

        Returns:
            Flattened list of DiffChunks
        """
        diff_chunks = []
        for chunk in chunks:
            diff_chunks.extend(chunk.get_chunks())
        return diff_chunks
