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

from loguru import logger

from codestory.core.data.chunk import Chunk
from codestory.core.data.composite_diff_chunk import CompositeDiffChunk
from codestory.core.data.diff_chunk import DiffChunk
from codestory.core.semantic_grouper.chunk_lableler import AnnotatedChunk, ChunkLabeler
from codestory.core.semantic_grouper.context_manager import ContextManager
from codestory.core.semantic_grouper.union_find import UnionFind


class SemanticGrouper:
    """
    Groups chunks semantically based on overlapping symbol signatures.

    The grouper flattens composite chunks into individual DiffChunks, generates
    semantic signatures for each chunk, and groups chunks with overlapping signatures
    using a union-find algorithm. Chunks that cannot be analyzed are placed in a
    fallback group for safety.
    """

    def group_chunks(
        self, chunks: list[Chunk], context_manager: ContextManager
    ) -> list[CompositeDiffChunk]:
        """
        Group chunks semantically based on overlapping symbol signatures.

        Args:
            chunks: List of chunks to group semantically

        Returns:
            List of semantic groups, with fallback group last if it exists

        Raises:
            ValueError: If chunks list is empty
        """
        if not chunks:
            return []

        # Step 2: Generate signatures for each chunk
        annotated_chunks = ChunkLabeler.annotate_chunks(chunks, context_manager)

        # Step 3: Separate chunks that can be analyzed from those that cannot
        analyzable_chunks = []
        fallback_chunks = []

        for annotated_chunk in annotated_chunks:
            if annotated_chunk.signature is not None:
                analyzable_chunks.append(annotated_chunk)
            else:
                # TODO smarter fallback logic, for example using file extensions
                fallback_chunks.append(annotated_chunk.chunk)

        # Step 5: Group analyzable chunks using Union-Find based on overlapping signatures
        semantic_groups = []
        if analyzable_chunks:
            grouped_chunks = self._group_by_overlapping_signatures(analyzable_chunks)
            semantic_groups.extend(grouped_chunks)

        # Step 6: Add fallback group if any chunks couldn't be analyzed
        if fallback_chunks:
            fallback_group = CompositeDiffChunk(
                chunks=fallback_chunks,
            )
            semantic_groups.append(fallback_group)

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

    def _group_by_overlapping_signatures(
        self,
        annotated_chunks: list[AnnotatedChunk],
    ) -> list[CompositeDiffChunk]:
        """
        Group chunks with overlapping signatures using an efficient
        inverted index and Union-Find algorithm.
        Also groups chunks that share the same scope (if scope is not None).
        """
        if not annotated_chunks:
            return []

        logger.debug(f"annotated chunks count={len(annotated_chunks)}")

        chunk_ids = [i for i in range(len(annotated_chunks))]
        signatures = [ac.signature for ac in annotated_chunks]
        if not chunk_ids:
            return []

        uf = UnionFind(chunk_ids)

        # Step 1: Create an inverted index from symbol -> list of chunk_ids
        symbol_to_chunks: dict[str, list[int]] = defaultdict(list)
        scope_to_chunks: dict[str, list[int]] = defaultdict(list)
        for i, sig in enumerate(signatures):
            # TODO: Consider splitting into two merge classes - one for symbol-based
            # merging and another for scope-based merging to clarify behavior.
            for symbol in sig.def_new_symbols | sig.def_old_symbols:
                symbol_to_chunks[symbol].append(i)
            for scope in sig.scopes:
                scope_to_chunks[scope].append(i)

        # Step 2: Union chunks that share common symbols
        for _, ids in symbol_to_chunks.items():
            if len(ids) > 1:
                first_chunk_id = ids[0]
                for i in range(1, len(ids)):
                    uf.union(first_chunk_id, ids[i])

        # Step 2.5: Union chunks that share common scopes
        for _, ids in scope_to_chunks.items():
            if len(ids) > 1:
                first_chunk_id = ids[0]
                for i in range(1, len(ids)):
                    uf.union(first_chunk_id, ids[i])

        # Step 3: Group chunks by their root in the Union-Find structure
        groups: dict[int, list[Chunk]] = defaultdict(list)
        for i in range(len(signatures)):
            root = uf.find(i)
            original_chunk = annotated_chunks[i].chunk
            groups[root].append(original_chunk)

        # Convert to SemanticGroup objects
        return [
            CompositeDiffChunk(chunks=group_chunks) for group_chunks in groups.values()
        ]
