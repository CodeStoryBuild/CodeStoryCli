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
"""
Utilities for preparing annotated patches from chunks for summarization.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from codestory.core.data.chunk import Chunk
from codestory.core.data.immutable_chunk import ImmutableChunk
from codestory.core.diff_generation.diff_generator import DiffGenerator
from codestory.core.semantic_grouper.chunk_lableler import AnnotatedChunk, ChunkLabeler
from codestory.core.semantic_grouper.query_manager import QueryManager
from codestory.core.utils.patch import truncate_patch, truncate_patch_bytes

if TYPE_CHECKING:
    from codestory.core.semantic_grouper.context_manager import ContextManager


DEFAULT_PATCH_CUTOFF_CHARS = 1000


def generate_annotated_patches(
    chunks: list[Chunk | ImmutableChunk],
    context_manager: ContextManager,
    diff_generator: DiffGenerator,
    patch_cutoff_chars: int = DEFAULT_PATCH_CUTOFF_CHARS,
) -> list[list[dict]]:
    """
    Generate annotated patches for a list of chunks.

    Args:
        chunks: List of Chunk or ImmutableChunk objects
        context_manager: ContextManager for semantic analysis
        diff_generator: DiffGenerator for patch generation
        patch_cutoff_chars: Maximum characters per patch before truncation

    Returns:
        List of annotated patches (each patch is a list of dicts with patch info)
    """
    patches = []
    for chunk in chunks:
        patch = generate_annotated_patch(
            chunk=chunk,
            context_manager=context_manager,
            diff_generator=diff_generator,
            patch_cutoff_chars=patch_cutoff_chars,
        )
        patches.append(patch)
    return patches


def generate_annotated_patch(
    chunk: Chunk | ImmutableChunk,
    context_manager: ContextManager,
    diff_generator: DiffGenerator,
    patch_cutoff_chars: int = DEFAULT_PATCH_CUTOFF_CHARS,
) -> list[dict]:
    """
    Generate an annotated patch for a single chunk.

    Args:
        chunk: A Chunk or ImmutableChunk object
        context_manager: ContextManager for semantic analysis
        diff_generator: DiffGenerator for patch generation
        patch_cutoff_chars: Maximum characters per patch before truncation

    Returns:
        List of dicts containing patch info with semantic annotations
    """
    if isinstance(chunk, ImmutableChunk):
        return _generate_immutable_annotated_patch(chunk, patch_cutoff_chars)
    else:
        # For regular Chunks, first annotate them
        annotated_chunk = ChunkLabeler.annotate_chunk(
            chunk=chunk,
            context_manager=context_manager,
        )
        if annotated_chunk is None:
            # Fallback: just return basic patch info
            return _generate_basic_chunk_patch(
                chunk, diff_generator, patch_cutoff_chars
            )
        return generate_annotated_chunk_patch(
            annotated_chunk, diff_generator, patch_cutoff_chars
        )


def _generate_immutable_annotated_patch(
    chunk: ImmutableChunk,
    patch_cutoff_chars: int,
) -> list[dict]:
    """Generate patch info for an immutable chunk (no semantic analysis)."""
    patch_json = {}
    patch_json["file_path"] = chunk.canonical_path.decode("utf-8", errors="replace")
    patch_json["git_patch"] = truncate_patch_bytes(
        chunk.file_patch, patch_cutoff_chars
    ).decode("utf-8", errors="replace")
    return [patch_json]


def _generate_basic_chunk_patch(
    chunk: Chunk,
    diff_generator: DiffGenerator,
    patch_cutoff_chars: int,
) -> list[dict]:
    """Generate basic patch info for a chunk without semantic annotations."""
    annotated_patch = []
    diff_chunks = chunk.get_chunks()
    for diff_chunk in diff_chunks:
        patch = truncate_patch(diff_generator.get_patch(diff_chunk), patch_cutoff_chars)
        patch_json = {"git_patch": patch}
        annotated_patch.append(patch_json)
    return annotated_patch


def generate_annotated_chunk_patch(
    annotated_chunk: AnnotatedChunk,
    diff_generator: DiffGenerator,
    patch_cutoff_chars: int,
) -> list[dict]:
    """Generate annotated patch info for an annotated chunk with semantic information."""
    annotated_patch = []
    chunks = annotated_chunk.chunk.get_chunks()
    signatures = (
        annotated_chunk.signature.signatures
        if annotated_chunk.signature
        else [None] * len(chunks)
    )
    for chunk, signature in zip(
        chunks,
        signatures,
        strict=True,
    ):
        patch = truncate_patch(diff_generator.get_patch(chunk), patch_cutoff_chars)
        patch_json = {}

        patch_json["git_patch"] = patch

        # add only relevant info
        if signature is not None:
            # remove extra symbol info for cleaner output
            # eg "foo identifier_class python" -> "foo"
            new_symbols_cleaned = {
                QueryManager.extract_qualified_symbol_name(sym)
                for sym in signature.def_new_symbols_filtered
            }
            old_symbols_cleaned = {
                QueryManager.extract_qualified_symbol_name(sym)
                for sym in signature.def_old_symbols_filtered
            }

            modified_symbols = old_symbols_cleaned.intersection(new_symbols_cleaned)
            added_symbols = new_symbols_cleaned - modified_symbols
            removed_symbols = old_symbols_cleaned - modified_symbols

            if annotated_chunk.signature.total_signature.languages:
                patch_json["languages"] = list(
                    annotated_chunk.signature.total_signature.languages
                )
            if modified_symbols:
                patch_json["modified_symbols"] = list(modified_symbols)
            if added_symbols:
                patch_json["added_symbols"] = list(added_symbols)
            if removed_symbols:
                patch_json["removed_symbols"] = list(removed_symbols)
            if signature.new_fqns or signature.old_fqns:
                all_fqns = signature.new_fqns | signature.old_fqns
                # Format: "file.py:Class.method (function)"
                patch_json["affected_scopes"] = [
                    f"{typed_fqn.fqn} ({typed_fqn.fqn_type})" for typed_fqn in all_fqns
                ]

        annotated_patch.append(patch_json)

    return annotated_patch
