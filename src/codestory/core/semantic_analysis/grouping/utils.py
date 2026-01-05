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
"""Utility functions for semantic grouping of chunks.

Extracted from SemanticGrouper for reuse in finalize_smart_merge and
other contexts.
"""

from collections import defaultdict
from pathlib import Path
from typing import Literal

from codestory.core.diff.data.composite_container import CompositeContainer
from codestory.core.logging.progress_manager import ProgressBarManager
from codestory.core.semantic_analysis.annotation.chunk_lableler import (
    AnnotatedContainer,
)
from codestory.core.semantic_analysis.grouping.union_find import UnionFind


def group_by_overlapping_signatures(
    annotated_chunks: list[AnnotatedContainer],
) -> list[CompositeContainer]:
    """Group chunks with overlapping signatures using an efficient inverted index and
    Union-Find algorithm. Also groups chunks that share the same scope (if scope is not
    None).

    Args:
        annotated_chunks: List of AnnotatedChunk objects with signatures

    Returns:
        List of CompositeDiffChunk objects grouped by overlapping signatures
    """
    if not annotated_chunks:
        return []

    chunk_ids = list(range(len(annotated_chunks)))

    uf = UnionFind(chunk_ids)

    pbar = ProgressBarManager.get_pbar()
    if pbar is not None:
        pbar.set_postfix({"phase": f"semantic grouping 0/{len(annotated_chunks)}"})

    # Create an inverted index from symbol/scope -> list of chunk_ids
    symbol_to_chunks: dict[str, list[int]] = defaultdict(list)
    scope_to_chunks: dict[str, list[int]] = defaultdict(list)
    for i, ac in enumerate(annotated_chunks):
        if pbar is not None:
            pbar.set_postfix(
                {
                    "phase": f"semantic grouping {i + 1}/{len(annotated_chunks)}",
                }
            )

        sig = ac.signature
        if not sig.has_valid_sig():
            continue

        for symbol in (
            sig.total_signature.def_new_symbols | sig.total_signature.def_old_symbols
        ):
            symbol_to_chunks[symbol].append(i)
        # Convert named scope lists to sets for union operation
        for scope in (
            sig.total_signature.new_structural_scopes
            | sig.total_signature.old_structural_scopes
        ):
            scope_to_chunks[scope].append(i)

    # Union chunks that share common symbols
    total_symbols = len(symbol_to_chunks)
    for i, (_, ids) in enumerate(symbol_to_chunks.items()):
        if pbar is not None:
            pbar.set_postfix(
                {
                    "phase": f"union semantic symbols {i + 1}/{total_symbols}",
                }
            )
        if len(ids) > 1:
            first_chunk_id = ids[0]
            for j in range(1, len(ids)):
                uf.union(first_chunk_id, ids[j])

    # Union chunks that share common scopes
    total_scopes = len(scope_to_chunks)
    for i, (_, ids) in enumerate(scope_to_chunks.items()):
        if pbar is not None:
            pbar.set_postfix(
                {
                    "phase": f"union semantic scopes {i + 1}/{total_scopes}",
                }
            )
        if len(ids) > 1:
            first_chunk_id = ids[0]
            for j in range(1, len(ids)):
                uf.union(first_chunk_id, ids[j])

    # Group chunks by their root in the Union-Find structure
    groups: dict[int, list[AnnotatedContainer]] = defaultdict(list)
    for i in range(len(annotated_chunks)):
        root = uf.find(i)
        original_chunk = annotated_chunks[i]
        groups[root].append(original_chunk)

    # Convert to CompositeDiffChunk objects
    return [CompositeContainer(containers=containers) for containers in groups.values()]


def get_fallback_signature(
    path: bytes,
    strategy: Literal[
        "all_together", "by_file_path", "by_file_name", "by_file_extension"
    ],
) -> str:
    """Get a signature for a file path based on the fallback grouping strategy.

    Args:
        path: The file path as bytes
        strategy: The grouping strategy to use

    Returns:
        A string signature for grouping
    """
    path_str = path.decode("utf-8", errors="replace")

    if strategy == "all_together":
        return "all"
    elif strategy == "by_file_path":
        return path_str
    elif strategy == "by_file_name":
        return Path(path_str).name
    elif strategy == "by_file_extension":
        return Path(path_str).suffix or "(no extension)"
    else:
        return "all"


def group_fallback_chunks(
    fallback_chunks: list[AnnotatedContainer],
    strategy: Literal[
        "all_together",
        "by_file_path",
        "by_file_name",
        "by_file_extension",
        "all_alone",
    ],
) -> list[CompositeContainer]:
    """Group fallback chunks based on the configured strategy using union-find.

    Each chunk can contain multiple diff chunks with different paths.
    Chunks are grouped if they share any common signature based on the strategy.

    Args:
        fallback_chunks: Chunks that failed annotation (can include ImmutableDiffChunks)
        strategy: The grouping strategy to use

    Returns:
        List of composite chunks grouped according to the strategy
    """
    if not fallback_chunks:
        return []

    if strategy == "all_alone":
        # no fallback grouping, just leave each chunk as is
        return fallback_chunks

    # Build signature sets for each chunk
    chunk_signatures: list[set[str]] = []
    pbar = ProgressBarManager.get_pbar()
    if pbar is not None:
        pbar.set_postfix({"phase": f"fallback grouping 0/{len(fallback_chunks)}"})

    for i, chunk in enumerate(fallback_chunks):
        if pbar is not None:
            pbar.set_postfix(
                {
                    "phase": f"fallback grouping {i + 1}/{len(fallback_chunks)}",
                }
            )
        # Get all canonical paths for this chunk
        paths = chunk.canonical_paths()
        # Generate signatures for each path
        sigs = {get_fallback_signature(path, strategy) for path in paths}
        chunk_signatures.append(sigs)

    # Use union-find to group chunks with overlapping signatures
    chunk_ids = list(range(len(fallback_chunks)))
    uf = UnionFind(chunk_ids)

    # Create inverted index: signature -> list of chunk indices
    sig_to_chunks: dict[str, list[int]] = defaultdict(list)
    for i, sigs in enumerate(chunk_signatures):
        for sig in sigs:
            sig_to_chunks[sig].append(i)

    # Union chunks that share common signatures
    total_sigs = len(sig_to_chunks)
    for i, (_, chunk_indices) in enumerate(sig_to_chunks.items()):
        if pbar is not None:
            pbar.set_postfix({"phase": f"union fallback chunks {i + 1}/{total_sigs}"})
        if len(chunk_indices) > 1:
            first = chunk_indices[0]
            for j in range(1, len(chunk_indices)):
                uf.union(first, chunk_indices[j])

    # Group chunks by their root in union-find
    groups: dict[int, list[AnnotatedContainer]] = defaultdict(list)
    for i in range(len(fallback_chunks)):
        root = uf.find(i)
        groups[root].append(fallback_chunks[i])

    return [CompositeContainer(containers=containers) for containers in groups.values()]
