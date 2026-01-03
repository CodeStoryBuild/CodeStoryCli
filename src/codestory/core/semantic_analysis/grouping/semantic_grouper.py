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

from codestory.core.diff.data.atomic_container import AtomicContainer
from codestory.core.semantic_analysis.annotation.chunk_lableler import (
    ContainerLabler,
)
from codestory.core.semantic_analysis.annotation.context_manager import ContextManager
from codestory.core.semantic_analysis.grouping.utils import (
    group_by_overlapping_signatures,
    group_fallback_chunks,
)


class SemanticGrouper:
    """Groups chunks semantically based on overlapping symbol signatures.

    The grouper flattens composite chunks into individual DiffChunks,
    generates semantic signatures for each chunk, and groups chunks with
    overlapping signatures using a union-find algorithm. Chunks that
    cannot be analyzed are placed in fallback groups based on the
    configured strategy.

    ImmutableDiffChunks (binary/large files) are automatically placed in
    fallback groups since they cannot be semantically analyzed.
    """

    def __init__(
        self,
        context_manager: ContextManager,
        fallback_grouping_strategy: Literal[
            "all_together",
            "by_file_path",
            "by_file_name",
            "by_file_extension",
            "all_alone",
        ] = "all_together",
    ):
        """Initialize the SemanticGrouper with a fallback grouping strategy.

        Args:
            fallback_grouping_strategy: Strategy for grouping chunks that fail annotation.
                - 'all_together': All fallback chunks in one group (default)
                - 'by_file_path': Group by complete file path
                - 'by_file_name': Group by file name only
                - 'by_file_extension': Group by file extension
        """
        self.context_manager = context_manager
        self.fallback_grouping_strategy = fallback_grouping_strategy

    def group(
        self,
        containers: list[AtomicContainer],
    ) -> list[AtomicContainer]:
        """Group chunks semantically based on overlapping symbol signatures."""
        if not containers:
            return []

        # Generate signatures for regular chunks only
        annotated_chunks = ContainerLabler.annotate_containers(
            containers, self.context_manager
        )

        # Separate chunks that can be analyzed from those that cannot
        analyzable_chunks = []
        fallback_chunks = []

        for annotated_chunk in annotated_chunks:
            if annotated_chunk.signature.has_valid_sig():
                analyzable_chunks.append(annotated_chunk)
            else:
                fallback_chunks.append(annotated_chunk)

        # Group analyzable chunks using Union-Find based on overlapping signatures
        semantic_groups = []
        if analyzable_chunks:
            grouped_chunks = group_by_overlapping_signatures(analyzable_chunks)
            semantic_groups.extend(grouped_chunks)

        if fallback_chunks:
            fallback_groups = group_fallback_chunks(
                fallback_chunks, self.fallback_grouping_strategy
            )
            semantic_groups.extend(fallback_groups)

        return semantic_groups
