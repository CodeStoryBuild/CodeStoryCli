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
from codestory.core.diff.data.composite_container import CompositeContainer
from codestory.core.diff.patch.patch_generator import PatchGenerator
from codestory.core.diff.utils.chunk_merger import merge_container
from codestory.core.logging.progress_manager import ProgressBarManager
from codestory.core.semantic_analysis.annotation.chunk_lableler import (
    AnnotatedContainer,
    ContainerLabler,
    Signature,
    TypedFQN,
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


def prioritize_longer_fqns(fqns: set[TypedFQN]) -> list[TypedFQN]:
    """Prioritize longer FQNs as they will likely be more meaningful."""
    return sorted(fqns, key=lambda f: (-len(f.fqn), f.fqn))


def generate_annotated_chunk_patch(
    annotated_container: AnnotatedContainer,
    patch_generator: PatchGenerator,
    patch_cutoff_chars: int,
) -> str:
    """Generate an XML-formatted annotated patch with semantic information per file.

    Returns an XML string with the following structure per file:
    <change_group index="...">
      <metadata>
        <language>...</language>
        <modified_scopes>...</modified_scopes>
        ...
      </metadata>
      <patch>
        ...
      </patch>
    </change_group>
    """
    atomic_chunks = annotated_container.get_atomic_chunks()
    chunk_signatures = annotated_container.signature.signatures

    # Partition by canonical path
    from collections import defaultdict

    groups = defaultdict(list)
    for chunk, sig in zip(atomic_chunks, chunk_signatures, strict=False):
        path = chunk.canonical_path()
        groups[path].append((chunk, sig))

    file_sections = []

    # Sort paths for consistency
    for i, path in enumerate(sorted(groups.keys())):
        chunk_sig_pairs = groups[path]
        group_chunks = [p[0] for p in chunk_sig_pairs]
        group_signatures = [sig for _, sig in chunk_sig_pairs if sig is not None]

        # Combine signatures for this file
        sig = Signature.from_signatures(group_signatures) if group_signatures else None

        # Generate patch for this group
        group_container = CompositeContainer(containers=group_chunks)
        diff_bytes = patch_generator.get_patch(group_container, is_bytes=True)
        truncated_diff_bytes = truncate_patch_bytes(diff_bytes, patch_cutoff_chars)
        patch = truncated_diff_bytes.decode("utf-8", errors="replace")

        # Start XML block
        lines = [f'<change_group index="{i + 1}">']

        if sig:
            lines.append("<metadata>")
            # Programming language
            if sig.languages:
                lang = sorted(sig.languages)[0]
                lines.append(f"<language>{lang}</language>")

            # Affected scopes
            modified_fqns = sig.new_fqns.intersection(sig.old_fqns)
            added_fqns = sig.new_fqns - modified_fqns
            removed_fqns = sig.old_fqns - modified_fqns

            if modified_fqns:
                top_mod_fqns = [
                    f"{fqn.fqn} ({fqn.fqn_type})"
                    for fqn in prioritize_longer_fqns(modified_fqns)[:3]
                ]
                lines.append(
                    f"<modified_scopes>{', '.join(top_mod_fqns)}</modified_scopes>"
                )

            if added_fqns:
                top_add_fqns = [
                    f"{fqn.fqn} ({fqn.fqn_type})"
                    for fqn in prioritize_longer_fqns(added_fqns)[:3]
                ]
                lines.append(f"<added_scopes>{', '.join(top_add_fqns)}</added_scopes>")

            if removed_fqns:
                top_rem_fqns = [
                    f"{fqn.fqn} ({fqn.fqn_type})"
                    for fqn in prioritize_longer_fqns(removed_fqns)[:3]
                ]
                lines.append(
                    f"<removed_scopes>{', '.join(top_rem_fqns)}</removed_scopes>"
                )

            # Symbols
            new_symbols_cleaned = {
                QueryManager.extract_qualified_symbol_name(s)
                for s in sig.def_new_symbols_filtered
            }
            old_symbols_cleaned = {
                QueryManager.extract_qualified_symbol_name(s)
                for s in sig.def_old_symbols_filtered
            }

            modified_symbols = old_symbols_cleaned.intersection(new_symbols_cleaned)
            added_symbols = new_symbols_cleaned - modified_symbols
            removed_symbols = old_symbols_cleaned - modified_symbols

            if modified_symbols:
                top_mod = prioritize_longer_symbols(modified_symbols)[:3]
                lines.append(
                    f"<modified_symbols>{', '.join(top_mod)}</modified_symbols>"
                )

            if added_symbols:
                top_add = prioritize_longer_symbols(added_symbols)[:3]
                lines.append(f"<added_symbols>{', '.join(top_add)}</added_symbols>")

            if removed_symbols:
                top_rem = prioritize_longer_symbols(removed_symbols)[:3]
                lines.append(f"<removed_symbols>{', '.join(top_rem)}</removed_symbols>")

            lines.append("</metadata>")

        # Patch block
        lines.append("<patch>")
        lines.append(patch.rstrip("\n"))
        lines.append("</patch>")
        lines.append("</change_group>")

        file_sections.extend(lines)

    return "\n".join(file_sections)
