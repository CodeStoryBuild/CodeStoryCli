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

from collections import defaultdict
from typing import Literal

from codestory.core.diff.data.atomic_container import AtomicContainer
from codestory.core.diff.data.composite_container import CompositeContainer
from codestory.core.diff.data.line_changes import Addition
from codestory.core.diff.data.standard_diff_chunk import StandardDiffChunk
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

        # Group context chunks first
        containers = self._group_context_chunks(containers)

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

    def _group_context_chunks(
        self, containers: list[AtomicContainer]
    ) -> list[AtomicContainer]:
        """Group context-only chunks with their nearest semantically meaningful neighbor."""
        # 1. Group by file
        files: dict[bytes, list[AtomicContainer]] = defaultdict(list)
        for container in containers:
            paths = container.canonical_paths()
            if paths:
                files[paths[0]].append(container)
            else:
                files[b""].append(container)

        final_containers = []

        for file_containers in files.values():
            if not file_containers:
                continue

            # 2. Sort by line anchor
            def get_sort_key(c: AtomicContainer):
                chunks = c.get_atomic_chunks()
                if chunks and isinstance(chunks[0], StandardDiffChunk):
                    return chunks[0].get_sort_key()
                return (0, 0)

            sorted_containers = sorted(file_containers, key=get_sort_key)

            # 3. Grouping logic
            processed_containers: list[AtomicContainer] = []
            pending_context: list[AtomicContainer] = []

            for container in sorted_containers:
                if self._is_context_container(container):
                    pending_context.append(container)
                else:
                    # Non-context chunk found.
                    # Group all pending context chunks with THIS chunk (below preference)
                    if pending_context:
                        group = CompositeContainer(pending_context + [container])
                        processed_containers.append(group)
                        pending_context = []  # Reset
                    else:
                        processed_containers.append(container)

            # 4. Handle trailing context (no code below, so attach to closest above)
            if pending_context:
                if processed_containers:
                    # Attach trailing context to the last non-context group/chunk above
                    last_item = processed_containers[-1]
                    if isinstance(last_item, CompositeContainer):
                        new_group = CompositeContainer(
                            last_item.containers + pending_context
                        )
                    else:
                        new_group = CompositeContainer([last_item] + pending_context)
                    processed_containers[-1] = new_group
                else:
                    # No non-context chunks in the file at all - group all context together
                    if len(pending_context) > 1:
                        processed_containers.append(CompositeContainer(pending_context))
                    else:
                        processed_containers.append(pending_context[0])

            final_containers.extend(processed_containers)

        return final_containers

    def _is_context_container(self, container: AtomicContainer) -> bool:
        """Check if a container consists entirely of context lines (whitespace/comments)."""
        atomic_chunks = container.get_atomic_chunks()
        standard_chunks = [c for c in atomic_chunks if isinstance(c, StandardDiffChunk)]

        # If no standard chunks (e.g. binary/images), treat as non-context
        if not standard_chunks:
            return False

        for chunk in standard_chunks:
            if not chunk.has_content or not chunk.parsed_content:
                continue

            for item in chunk.parsed_content:
                if item.content.strip() == b"":
                    continue

                if isinstance(item, Addition):
                    file_path = chunk.new_file_path
                    commit_hash = chunk.new_hash
                    line_idx = item.abs_new_line - 1
                else:  # Removal
                    file_path = chunk.old_file_path
                    commit_hash = chunk.base_hash
                    line_idx = item.old_line - 1

                if not file_path:
                    return False

                ctx = self.context_manager.get_context(file_path, commit_hash)
                if not ctx:
                    return False

                if line_idx not in ctx.comment_map.pure_comment_lines:
                    return False

        return True
