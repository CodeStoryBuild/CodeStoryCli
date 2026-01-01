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
"""Utilities for preparing annotated patches from chunks for summarization."""

from __future__ import annotations

from typing import TYPE_CHECKING

from codestory.core.diff.data.atomic_container import AtomicContainer
from codestory.core.diff.patch.patch_generator import PatchGenerator
from codestory.core.diff.utils.chunk_merger import merge_container
from codestory.core.logging.progress_manager import ProgressBarManager
from codestory.core.semantic_analysis.annotation.chunk_lableler import (
    AnnotatedContainer,
    ContainerLabler,
)
from codestory.core.semantic_analysis.annotation.utils import truncate_patch_bytes
from codestory.core.semantic_analysis.mappers.query_manager import QueryManager

if TYPE_CHECKING:
    from codestory.core.semantic_analysis.annotation.context_manager import (
        ContextManager,
    )


DEFAULT_PATCH_CUTOFF_CHARS = 1000


def generate_annotated_patches(
    containers: list[AtomicContainer],
    context_manager: ContextManager,
    patch_generator: PatchGenerator,
    patch_cutoff_chars: int = DEFAULT_PATCH_CUTOFF_CHARS,
) -> list[str]:
    """Generate annotated patches for a list of containers as markdown strings.

    Args:
        containers: List of AtomicContainer objects
        context_manager: ContextManager for semantic analysis
        patch_generator: PatchGenerator for patch generation
        patch_cutoff_chars: Maximum characters per patch before truncation

    Returns:
        List of markdown-formatted annotated patches, one per container
    """
    patches = []
    pbar = ProgressBarManager.get_pbar()
    if pbar is not None:
        pbar.set_postfix(
            {"phase": "preparing patches", "chunks": f"0/{len(containers)}"}
        )

    for i, container in enumerate(containers):
        if pbar is not None:
            pbar.set_postfix(
                {"phase": "preparing patches", "chunks": f"{i + 1}/{len(containers)}"}
            )
        patch = generate_annotated_patch(
            container=container,
            context_manager=context_manager,
            patch_generator=patch_generator,
            patch_cutoff_chars=patch_cutoff_chars,
        )
        patches.append(patch)
    return patches


def generate_annotated_patch(
    container: AtomicContainer,
    context_manager: ContextManager,
    patch_generator: PatchGenerator,
    patch_cutoff_chars: int = DEFAULT_PATCH_CUTOFF_CHARS,
) -> str:
    """Generate a markdown-formatted annotated patch for a single container."""
    merged_container = merge_container(container)

    annotated_container = ContainerLabler.annotate_container(
        container=merged_container,
        context_manager=context_manager,
    )

    return generate_annotated_chunk_patch(
        annotated_container, patch_generator, patch_cutoff_chars
    )


def prioritize_longer_symbols(symbols: set[str]) -> list[str]:
    """Prioritize longer symbol names as they will likely be more meaningful."""
    return sorted(symbols, key=lambda s: (-len(s), s))


def generate_annotated_chunk_patch(
    annotated_chunk: AnnotatedContainer,
    patch_generator: PatchGenerator,
    patch_cutoff_chars: int,
    symbol_limit: int = 5,
) -> str:
    """Generate a markdown-formatted annotated patch with semantic information.

    Returns a markdown string with the following structure:
    - Optional metadata line (languages, scopes)
    - Optional symbols line (modified/added/removed)
    - Fenced diff code block
    """
    diff_map = patch_generator.generate_diff([annotated_chunk])
    # sort by file name to keep order consistent
    ordered_diffs = sorted(diff_map.items(), key=lambda kv: kv[0])

    truncated_sections = []
    for _, diff_bytes in ordered_diffs:
        truncated_sections.append(truncate_patch_bytes(diff_bytes, patch_cutoff_chars))
    patch_bytes = b"\n".join(truncated_sections)
    patch = patch_bytes.decode("utf-8", errors="replace")

    lines = []

    if annotated_chunk.signature.has_valid_sig():
        signature = annotated_chunk.signature.total_signature

        # Extract and clean symbol names
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

        # Build metadata line: Languages | Scopes
        metadata_parts = []

        if signature.languages:
            langs = ", ".join(signature.languages)
            metadata_parts.append(f"**Languages:** {langs}")

        if signature.new_fqns or signature.old_fqns:
            all_fqns = signature.new_fqns | signature.old_fqns
            # Prioritize scopes
            scopes = [f"`{fqn.fqn}` ({fqn.fqn_type})" for fqn in all_fqns]
            metadata_parts.append(f"**Scopes:** {', '.join(scopes[:3])}")

        if metadata_parts:
            lines.append(" | ".join(metadata_parts))

        # Build symbols line: Modified: x, y | Added: z
        symbol_parts = []

        if modified_symbols:
            syms = prioritize_longer_symbols(modified_symbols)[:symbol_limit]
            symbol_parts.append(f"Modified: `{'`, `'.join(syms)}`")

        if added_symbols:
            syms = prioritize_longer_symbols(added_symbols)[:symbol_limit]
            symbol_parts.append(f"Added: `{'`, `'.join(syms)}`")

        if removed_symbols:
            syms = prioritize_longer_symbols(removed_symbols)[:symbol_limit]
            symbol_parts.append(f"Removed: `{'`, `'.join(syms)}`")

        if symbol_parts:
            lines.append(" | ".join(symbol_parts))

    # Add the diff block
    lines.append(f"```diff\n{patch}\n```")

    return "\n".join(lines)
