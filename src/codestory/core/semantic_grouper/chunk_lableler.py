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

from dataclasses import dataclass

from loguru import logger

from codestory.core.data.chunk import Chunk
from codestory.core.data.diff_chunk import DiffChunk
from codestory.core.semantic_grouper.context_manager import (
    AnalysisContext,
    ContextManager,
)


@dataclass(frozen=True)
class ChunkSignature:
    """Represents the semantic signature of a chunk."""

    def_new_symbols: set[str]  # Symbols defined in the new version
    def_old_symbols: set[str]  # Symbols defined in the old version
    extern_new_symbols: set[
        str
    ]  # Symbols referenced but not defined in the new version
    extern_old_symbols: set[
        str
    ]  # Symbols referenced but not defined in the old version
    scopes: set[
        str
    ]  # Scopes that the chunk contains. Currently used only for equality checks.
    # TODO: Consider storing more descriptive scope metadata if needed (e.g., scope types or fully-qualified names).


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
                (
                    def_new_symbols,
                    def_old_symbols,
                    extern_new_symbols,
                    extern_old_symbols,
                    scopes,
                ) = signature_result

                chunk_signature = ChunkSignature(
                    def_new_symbols=def_new_symbols,
                    def_old_symbols=def_old_symbols,
                    extern_new_symbols=extern_new_symbols,
                    extern_old_symbols=extern_old_symbols,
                    scopes=scopes,
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
        tuple[set[str], set[str], set[str], set[str], set[str]] | None
    ):  # Return type is now Optional[tuple[Set[str], Optional[str]]]
        """
        Generate a semantic signature for a single chunk.
        Returns tuple of (symbols, scope) if analysis succeeds, None if analysis fails.
        Scope is determined by the LCA scope of the first diff chunk that has a scope.
        """
        if not diff_chunks:
            return (
                set(),
                set(),
                set(),
                set(),
                set(),
            )  # An empty chunk has a valid, empty signature with no scope

        def_new_symbols_acc = set()
        def_old_symbols_acc = set()
        extern_new_symbols_acc = set()
        extern_old_symbols_acc = set()
        total_scope = set()

        for diff_chunk in diff_chunks:
            # try:
            if not ChunkLabeler._has_analysis_context(diff_chunk, context_manager):
                # If any diff chunk lacks context, the entire chunk fails analysis
                logger.debug(
                    f"No analysis for a diff chunk in {diff_chunk.canonical_path().decode('utf-8', errors='replace')}!"
                )
                continue

            (
                def_new_symbols,
                def_old_symbols,
                extern_new_symbols,
                extern_old_symbols,
                diff_chunk_scope,
            ) = ChunkLabeler._get_signature_for_diff_chunk(diff_chunk, context_manager)
            def_new_symbols_acc.update(def_new_symbols)
            def_old_symbols_acc.update(def_old_symbols)
            extern_new_symbols_acc.update(extern_new_symbols)
            extern_old_symbols_acc.update(extern_old_symbols)

            total_scope.update(diff_chunk_scope)

            # except Exception as e:
            #     logger.debug(
            #         f"Signature generation failed for diff chunk {diff_chunk.canonical_path().decode('utf-8', errors='replace')}: {e}"
            #     )
            #     return None

        logger.debug(
            f"Generated signature for chunk with def_new_symbols={def_new_symbols_acc}, def_old_symbols={def_old_symbols_acc}, extern_new_symbols={extern_new_symbols_acc}, extern_old_symbols={extern_old_symbols_acc}, scopes={total_scope}"
        )

        return (
            def_new_symbols_acc,
            def_old_symbols_acc,
            extern_new_symbols_acc,
            extern_old_symbols_acc,
            total_scope,
        )

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
    ) -> tuple[set[str], set[str], set[str], set[str], set[str]]:
        """
        Generate signature and scope information for a single DiffChunk based on affected line ranges.

        Args:
            diff_chunk: The DiffChunk to analyze
            context_manager: ContextManager with analysis contexts

        Returns:
            Tuple of (symbols, scope) in the affected line ranges.
            Scope is determined by the LCA scope of the chunk's line ranges.
        """
        def_old_symbols_acc = set()
        def_new_symbols_acc = set()
        extern_old_symbols_acc = set()
        extern_new_symbols_acc = set()
        chunk_scope = set()

        if diff_chunk.is_standard_modification or diff_chunk.is_file_rename:
            # For modifications/renames, analyze both old and new line ranges

            # Old version signature
            old_context = context_manager.get_context(diff_chunk.old_file_path, True)
            if old_context and diff_chunk.old_start is not None:
                old_end = diff_chunk.old_start + diff_chunk.old_len() - 1
                def_old_symbols, extern_old_symbols, old_scope = (
                    ChunkLabeler._get_signature_for_line_range(
                        diff_chunk.old_start, old_end, old_context
                    )
                )
                def_old_symbols_acc.update(def_old_symbols)
                extern_old_symbols_acc.update(extern_old_symbols)
                chunk_scope.update(old_scope)

            # New version signature
            new_context = context_manager.get_context(diff_chunk.new_file_path, False)
            abs_new_start = diff_chunk.get_abs_new_line_start()
            if new_context and abs_new_start is not None:
                abs_new_end = diff_chunk.get_abs_new_line_end() or abs_new_start
                def_new_symbols, extern_new_symbols, new_scope = (
                    ChunkLabeler._get_signature_for_line_range(
                        abs_new_start, abs_new_end, new_context
                    )
                )
                def_new_symbols_acc.update(def_new_symbols)
                extern_new_symbols_acc.update(extern_new_symbols)
                chunk_scope.update(new_scope)

        elif diff_chunk.is_file_addition:
            # For additions, analyze new version only
            new_context = context_manager.get_context(diff_chunk.new_file_path, False)
            abs_new_start = diff_chunk.get_abs_new_line_start()
            if new_context and abs_new_start is not None:
                abs_new_end = diff_chunk.get_abs_new_line_end() or abs_new_start
                def_new_symbols_acc, extern_new_symbols_acc, chunk_scope = (
                    ChunkLabeler._get_signature_for_line_range(
                        abs_new_start, abs_new_end, new_context
                    )
                )

        elif diff_chunk.is_file_deletion:
            # For deletions, analyze old version only
            old_context = context_manager.get_context(diff_chunk.old_file_path, True)
            if old_context and diff_chunk.old_start is not None:
                old_end = diff_chunk.old_start + diff_chunk.old_len() - 1
                def_old_symbols_acc, extern_old_symbols_acc, chunk_scope = (
                    ChunkLabeler._get_signature_for_line_range(
                        diff_chunk.old_start, old_end, old_context
                    )
                )

        # Return order must match the one expected by callers:
        # (def_new, def_old, extern_new, extern_old, chunk_scope)
        return (
            def_new_symbols_acc,
            def_old_symbols_acc,
            extern_new_symbols_acc,
            extern_old_symbols_acc,
            chunk_scope,
        )

    @staticmethod
    def _get_signature_for_line_range(
        start_line: int, end_line: int, context: AnalysisContext
    ) -> tuple[set[str], set[str], set[str]]:
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
        defined_range_symbols = set()
        extern_range_symbols = set()
        range_scope = set()

        if start_line < 1 or end_line < start_line:
            # Chunks that are pure deletions can fall into this
            return (defined_range_symbols, extern_range_symbols, range_scope)

        # convert to zero indexed
        start_index = start_line - 1
        end_index = end_line - 1

        # Collect symbols from fall lines in the range
        for line in range(start_index, end_index + 1):
            # Symbols explicitly defined on this line
            defined_line_symbols = context.symbol_map.modified_line_symbols.get(line)
            # Symbols referenced on this line but not defined in this file/version
            extern_line_symbols = context.symbol_map.extern_line_symbols.get(line)

            if defined_line_symbols:
                defined_range_symbols.update(defined_line_symbols)

            if extern_line_symbols:
                extern_range_symbols.update(extern_line_symbols)

            scopes = context.scope_map.scope_lines.get(line)

            if scopes:
                range_scope.update(scopes)

        return (defined_range_symbols, extern_range_symbols, range_scope)
