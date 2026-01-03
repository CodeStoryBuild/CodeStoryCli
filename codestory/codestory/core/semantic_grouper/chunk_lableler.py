"""
-----------------------------------------------------------------------------
/*
 * Copyright (C) 2025 CodeStory
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; Version 2.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, you can contact us at support@codestory.build
 */
-----------------------------------------------------------------------------
"""

from dataclasses import dataclass

from codestory.core.data.chunk import Chunk
from codestory.core.data.diff_chunk import DiffChunk
from loguru import logger

from .context_manager import AnalysisContext, ContextManager


@dataclass(frozen=True)
class ChunkSignature:
    """Represents the semantic signature of a chunk."""

    new_symbols: set[str]
    old_symbols: set[str]
    total_symbols: set[str]
    scopes: set[str]


@dataclass(frozen=True)
class AnnotatedChunk:
    """Represents a chunk along with its semantic signature."""

    chunk: Chunk
    signature: ChunkSignature | None


class ChunkLabeler:
    @staticmethod
    def annotate_chunks(
        original_chunks: list[Chunk],
        context_manager: ContextManager,
    ) -> list[AnnotatedChunk]:
        """
        Generate semantic signatures for each original chunk.
        """
        annotated_chunks = []

        for chunk in original_chunks:
            # Get all DiffChunks that belong to this original chunk
            chunk_diff_chunks = chunk.get_chunks()

            # Generate signature for this chunk, which might fail (return None)
            signature_result = ChunkLabeler._generate_signature_for_chunk(
                chunk_diff_chunks, context_manager
            )

            if signature_result is None:
                # Analysis failed for this chunk
                chunk_signature = None
            else:
                # Analysis succeeded, unpack symbols and scope
                total_symbols, new_symbols, old_symbols, scope = signature_result

                chunk_signature = ChunkSignature(
                    total_symbols=total_symbols,
                    new_symbols=new_symbols,
                    old_symbols=old_symbols,
                    scopes=scope,
                )

            annotated = AnnotatedChunk(
                chunk=chunk,
                signature=chunk_signature,
            )

            annotated_chunks.append(annotated)

        return annotated_chunks

    @staticmethod
    def _generate_signature_for_chunk(
        diff_chunks: list[DiffChunk], context_manager: ContextManager
    ) -> (
        tuple[set[str], set[str]] | None
    ):  # Return type is now Optional[tuple[Set[str], Optional[str]]]
        """
        Generate a semantic signature for a single chunk.
        Returns tuple of (symbols, scope) if analysis succeeds, None if analysis fails.
        Scope is determined by the LCA scope of the first diff chunk that has a scope.
        """
        if not diff_chunks:
            return (
                set(),
                None,
            )  # An empty chunk has a valid, empty signature with no scope

        total_symbols = set()
        new_symbols = set()
        old_symbols = set()
        total_scope = set()

        for diff_chunk in diff_chunks:
            try:
                if not ChunkLabeler._has_analysis_context(diff_chunk, context_manager):
                    # If any diff chunk lacks context, the entire chunk fails analysis
                    logger.debug(
                        f"No analysis for a diff chunk in {diff_chunk.canonical_path().decode('utf-8', errors='replace')}!"
                    )
                    continue

                (
                    total_chunk_symb,
                    total_chunk_new_symb,
                    total_chunk_old_symb,
                    diff_chunk_scope,
                ) = ChunkLabeler._get_signature_for_diff_chunk(
                    diff_chunk, context_manager
                )
                total_symbols.update(total_chunk_symb)
                new_symbols.update(total_chunk_new_symb)
                old_symbols.update(total_chunk_old_symb)
                total_scope.update(diff_chunk_scope)

            except Exception as e:
                logger.debug(
                    f"Signature generation failed for diff chunk {diff_chunk.canonical_path().decode('utf-8', errors='replace') if isinstance(diff_chunk.canonical_path(), bytes) else diff_chunk.canonical_path()}: {e}"
                )
                return None

        logger.debug(
            f"{total_symbols=}\n{new_symbols=}\n{old_symbols=}\n{total_scope=}\n{diff_chunks=}"
        )

        return (total_symbols, new_symbols, old_symbols, total_scope)

    @staticmethod
    def _has_analysis_context(
        diff_chunk: DiffChunk, context_manager: ContextManager
    ) -> bool:
        """
        Check if we have the necessary analysis context for a DiffChunk.

        Args:
            diff_chunk: The DiffChunk to check
            context_manager: ContextManager with analysis contexts

        Returns:
            True if we have context, False otherwise
        """
        if diff_chunk.is_standard_modification:
            # Need both old and new contexts
            file_path = diff_chunk.canonical_path()
            return context_manager.has_context(
                file_path, True
            ) and context_manager.has_context(file_path, False)

        elif diff_chunk.is_file_addition:
            # Need new context only
            return context_manager.has_context(diff_chunk.new_file_path, False)

        elif diff_chunk.is_file_deletion:
            # Need old context only
            return context_manager.has_context(diff_chunk.old_file_path, True)

        elif diff_chunk.is_file_rename:
            # Need both old and new contexts with respective paths
            return context_manager.has_context(
                diff_chunk.old_file_path, True
            ) and context_manager.has_context(diff_chunk.new_file_path, False)

        return False

    @staticmethod
    def _get_signature_for_diff_chunk(
        diff_chunk: DiffChunk, context_manager: ContextManager
    ) -> tuple[set[str], set[str], set[str], set[str]]:
        """
        Generate signature and scope information for a single DiffChunk based on affected line ranges.

        Args:
            diff_chunk: The DiffChunk to analyze
            context_manager: ContextManager with analysis contexts

        Returns:
            Tuple of (symbols, scope) in the affected line ranges.
            Scope is determined by the LCA scope of the chunk's line ranges.
        """
        total_symbols = set()
        old_symbols = set()
        new_symbols = set()
        chunk_scope = set()

        if diff_chunk.is_standard_modification:
            # For modifications, analyze both old and new line ranges
            file_path = diff_chunk.canonical_path()

            # Old version signature
            old_context = context_manager.get_context(file_path, True)
            if old_context and diff_chunk.old_start is not None:
                old_end = diff_chunk.old_start + diff_chunk.old_len() - 1
                old_symbols, old_scope = ChunkLabeler._get_signature_for_line_range(
                    diff_chunk.old_start, old_end, old_context
                )
                total_symbols.update(old_symbols)
                old_symbols.update(old_symbols)
                chunk_scope.update(old_scope)

            # New version signature
            new_context = context_manager.get_context(file_path, False)
            abs_new_start = diff_chunk.get_abs_new_line_start()
            if new_context and abs_new_start is not None:
                abs_new_end = diff_chunk.get_abs_new_line_end() or abs_new_start
                new_symbols, new_scope = ChunkLabeler._get_signature_for_line_range(
                    abs_new_start, abs_new_end, new_context
                )
                total_symbols.update(new_symbols)
                new_symbols.update(new_symbols)
                chunk_scope.update(new_scope)

        elif diff_chunk.is_file_addition:
            # For additions, analyze new version only
            new_context = context_manager.get_context(diff_chunk.new_file_path, False)
            abs_new_start = diff_chunk.get_abs_new_line_start()
            if new_context and abs_new_start is not None:
                abs_new_end = diff_chunk.get_abs_new_line_end() or abs_new_start
                total_symbols, chunk_scope = ChunkLabeler._get_signature_for_line_range(
                    abs_new_start, abs_new_end, new_context
                )
                new_symbols.update(total_symbols)

        elif diff_chunk.is_file_deletion:
            # For deletions, analyze old version only
            old_context = context_manager.get_context(diff_chunk.old_file_path, True)
            if old_context and diff_chunk.old_start is not None:
                old_end = diff_chunk.old_start + diff_chunk.old_len() - 1
                total_symbols, chunk_scope = ChunkLabeler._get_signature_for_line_range(
                    diff_chunk.old_start, old_end, old_context
                )
                old_symbols.update(total_symbols)

        elif diff_chunk.is_file_rename:
            # For renames, analyze both versions with their respective paths
            old_context = context_manager.get_context(diff_chunk.old_file_path, True)
            new_context = context_manager.get_context(diff_chunk.new_file_path, False)

            if old_context and diff_chunk.old_start is not None:
                old_end = diff_chunk.old_start + diff_chunk.old_len() - 1
                old_symbols, old_scope = ChunkLabeler._get_signature_for_line_range(
                    diff_chunk.old_start, old_end, old_context
                )
                total_symbols.update(old_symbols)
                old_symbols.update(old_symbols)
                chunk_scope.update(old_scope)

            abs_new_start = diff_chunk.get_abs_new_line_start()
            if new_context and abs_new_start is not None:
                abs_new_end = diff_chunk.get_abs_new_line_end() or abs_new_start
                new_symbols, new_scope = ChunkLabeler._get_signature_for_line_range(
                    abs_new_start, abs_new_end, new_context
                )
                total_symbols.update(new_symbols)
                new_symbols.update(new_symbols)
                chunk_scope.update(new_scope)

        return (total_symbols, new_symbols, old_symbols, chunk_scope)

    @staticmethod
    def _get_signature_for_line_range(
        start_line: int, end_line: int, context: AnalysisContext
    ) -> tuple[set[str], set[str]]:
        """
        Get signature and scope information for a specific line range using the analysis context.

        Args:
            start_line: Starting line number (1-indexed)
            end_line: Ending line number (1-indexed, inclusive)
            context: AnalysisContext containing symbol map and scope map

        Returns:
            Tuple of (symbols, scope) for the specified line range.
            Scope is the LCA scope, simplified to the scope of the first line.
        """
        range_symbols = set()
        range_scope = set()

        if start_line < 1 or end_line < start_line:
            # Chunks that are pure deletions can fall into this
            return (range_symbols, range_scope)

        # convert to zero indexed
        start_index = start_line - 1
        end_index = end_line - 1

        # Collect symbols from fall lines in the range
        for line in range(start_index, end_index + 1):
            line_symbols = context.symbol_map.line_symbols.get(line)

            if line_symbols:
                range_symbols.update(line_symbols)

            scopes = context.scope_map.scope_lines.get(line)

            if scopes:
                range_scope.update(scopes)

        return (range_symbols, range_scope)
