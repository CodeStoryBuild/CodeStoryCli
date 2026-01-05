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

from codestory.core.diff.data.atomic_chunk import AtomicDiffChunk
from codestory.core.diff.data.atomic_container import AtomicContainer
from codestory.core.diff.data.single_container import SingleContainer
from codestory.core.diff.data.standard_diff_chunk import StandardDiffChunk
from codestory.core.logging.progress_manager import ProgressBarManager
from codestory.core.semantic_analysis.annotation.context_manager import (
    AnalysisContext,
    ContextManager,
)


@dataclass(frozen=True)
class TypedFQN:
    """A fully qualified name with its type."""

    fqn: str
    fqn_type: str  # Type of the last scope component (e.g., "function", "class")

    def __hash__(self) -> int:
        return hash((self.fqn, self.fqn_type))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TypedFQN):
            return False
        return self.fqn == other.fqn and self.fqn_type == other.fqn_type


@dataclass(frozen=True)
class Signature:
    """Represents the semantic signature of a chunk."""

    file_names: set[str]
    commit_hashes: set[str]
    languages: set[str]  # Programming languages/File types of the signature
    new_structural_scopes: set[str]
    old_structural_scopes: set[str]
    new_fqns: set[TypedFQN]
    old_fqns: set[TypedFQN]
    def_new_symbols: set[str]
    def_old_symbols: set[str]
    extern_new_symbols: set[str]
    extern_old_symbols: set[str]
    def_new_symbols_filtered: set[str]
    def_old_symbols_filtered: set[str]
    extern_new_symbols_filtered: set[str]
    extern_old_symbols_filtered: set[str]

    @staticmethod
    def from_signatures(signatures: list["Signature"]) -> "Signature":
        # combine multiple signatures into one big one
        if len(signatures) == 0:
            return Signature(
                set(),
                set(),
                set(),
                set(),
                set(),
                set(),
                set(),
                set(),
                set(),
                set(),
                set(),
                set(),
                set(),
                set(),
                set(),
            )

        base_sig = next(sig for sig in signatures if sig is not None)
        base_file_names = set(base_sig.file_names)
        base_commit_hashes = set(base_sig.commit_hashes)
        base_languages = set(base_sig.languages)
        base_new_structural_scopes = set(base_sig.new_structural_scopes)
        base_old_structural_scopes = set(base_sig.old_structural_scopes)
        base_new_fqns = set(base_sig.new_fqns)
        base_old_fqns = set(base_sig.old_fqns)
        base_def_new_symbols = set(base_sig.def_new_symbols)
        base_def_old_symbols = set(base_sig.def_old_symbols)
        base_extern_new_symbols = set(base_sig.extern_new_symbols)
        base_extern_old_symbols = set(base_sig.extern_old_symbols)
        base_def_new_symbols_filtered = set(base_sig.def_new_symbols_filtered)
        base_def_old_symbols_filtered = set(base_sig.def_old_symbols_filtered)
        base_extern_new_symbols_filtered = set(base_sig.extern_new_symbols_filtered)
        base_extern_old_symbols_filtered = set(base_sig.extern_old_symbols_filtered)

        for s in signatures:
            if s is None or s is base_sig:
                continue

            base_file_names.update(s.file_names)
            base_commit_hashes.update(s.commit_hashes)
            base_languages.update(s.languages)
            base_new_structural_scopes.update(s.new_structural_scopes)
            base_old_structural_scopes.update(s.old_structural_scopes)
            base_new_fqns.update(s.new_fqns)
            base_old_fqns.update(s.old_fqns)
            base_def_new_symbols.update(s.def_new_symbols)
            base_def_old_symbols.update(s.def_old_symbols)
            base_extern_new_symbols.update(s.extern_new_symbols)
            base_extern_old_symbols.update(s.extern_old_symbols)
            base_def_new_symbols_filtered.update(s.def_new_symbols_filtered)
            base_def_old_symbols_filtered.update(s.def_old_symbols_filtered)
            base_extern_new_symbols_filtered.update(s.extern_new_symbols_filtered)
            base_extern_old_symbols_filtered.update(s.extern_old_symbols_filtered)

        return Signature(
            file_names=base_file_names,
            commit_hashes=base_commit_hashes,
            languages=base_languages,
            new_structural_scopes=base_new_structural_scopes,
            old_structural_scopes=base_old_structural_scopes,
            new_fqns=base_new_fqns,
            old_fqns=base_old_fqns,
            def_new_symbols=base_def_new_symbols,
            def_old_symbols=base_def_old_symbols,
            extern_new_symbols=base_extern_new_symbols,
            extern_old_symbols=base_extern_old_symbols,
            def_new_symbols_filtered=base_def_new_symbols_filtered,
            def_old_symbols_filtered=base_def_old_symbols_filtered,
            extern_new_symbols_filtered=base_extern_new_symbols_filtered,
            extern_old_symbols_filtered=base_extern_old_symbols_filtered,
        )


@dataclass(frozen=True)
class ContainerSignature:
    total_signature: Signature | None
    # ith index is signature for the ith chunk in container
    signatures: list[Signature | None]

    def has_valid_sig(self):
        return self.total_signature is not None


@dataclass(frozen=True)
class AnnotatedContainer(SingleContainer):
    """Represents a chunk along with its semantic signature."""

    signature: ContainerSignature


class ContainerLabler:
    @staticmethod
    def annotate_containers(
        containers: list[AtomicContainer],
        context_manager: ContextManager,
    ) -> list[AnnotatedContainer]:
        """Generate semantic signatures for each original chunk."""
        # ensure these chunks are merged
        annotated_chunks = []

        pbar = ProgressBarManager.get_pbar()
        if pbar is not None:
            pbar.set_postfix({"phase": f"annotating chunks 0/{len(containers)}"})

        for i, container in enumerate(containers):
            if pbar is not None:
                pbar.set_postfix(
                    {
                        "phase": f"annotating chunks {i + 1}/{len(containers)}",
                    }
                )

            annotated = ContainerLabler.annotate_container(
                container=container, context_manager=context_manager
            )

            annotated_chunks.append(annotated)

        return annotated_chunks

    @staticmethod
    def annotate_container(
        container: AtomicContainer, context_manager: ContextManager
    ) -> AnnotatedContainer:
        # Get all StandardDiffChunks that belong to this original chunk
        atomic_chunks = container.get_atomic_chunks()

        # Generate signature for this chunk, which might fail (return None)
        signatures = ContainerLabler._generate_signatures(
            atomic_chunks, context_manager
        )

        if all(sig is None for sig in signatures):
            # Analysis failed for this chunk
            chunk_signature = ContainerSignature(
                total_signature=None,
                signatures=signatures,
            )
        else:
            chunk_signature = ContainerSignature(
                total_signature=Signature.from_signatures(signatures),
                signatures=signatures,
            )

        return AnnotatedContainer(
            container=container,
            signature=chunk_signature,
        )

    @staticmethod
    def _generate_signatures(
        atomic_chunks: list[AtomicDiffChunk], context_manager: ContextManager
    ) -> list[Signature | None]:
        """Generate a semantic signature for each atomic chunk."""

        if not atomic_chunks:
            return []  # No diff chunks, return empty signature list

        signatures = []
        for atomic_chunk in atomic_chunks:
            # for now other types of atomic chunks cannot be analyzed
            if not isinstance(atomic_chunk, StandardDiffChunk):
                signatures.append(None)
                continue

            if not ContainerLabler._has_analysis_context(atomic_chunk, context_manager):
                signatures.append(None)
                continue

            signature = ContainerLabler._get_signature_for_diff_chunk(
                atomic_chunk, context_manager
            )
            signatures.append(signature)

        return signatures

    @staticmethod
    def _has_analysis_context(
        standard_diff_chunk: StandardDiffChunk, context_manager: ContextManager
    ) -> bool:
        """Check if we have the necessary analysis context for a StandardDiffChunk.

        Args:
            diff_chunk: The StandardDiffChunk to check
            context_manager: ContextManager with analysis contexts

        Returns:
            True if we have context, False otherwise
        """
        if standard_diff_chunk.is_standard_modification:
            # Need both old and new contexts
            file_path = standard_diff_chunk.canonical_path()
            return context_manager.has_context(
                file_path, standard_diff_chunk.base_hash
            ) and context_manager.has_context(file_path, standard_diff_chunk.new_hash)

        elif standard_diff_chunk.is_file_addition:
            # Need new context only
            return context_manager.has_context(
                standard_diff_chunk.new_file_path, standard_diff_chunk.new_hash
            )

        elif standard_diff_chunk.is_file_deletion:
            # Need old context only
            return context_manager.has_context(
                standard_diff_chunk.old_file_path, standard_diff_chunk.base_hash
            )

        elif standard_diff_chunk.is_file_rename:
            # Need both old and new contexts with respective paths
            return context_manager.has_context(
                standard_diff_chunk.old_file_path, standard_diff_chunk.base_hash
            ) and context_manager.has_context(
                standard_diff_chunk.new_file_path, standard_diff_chunk.new_hash
            )

        return False

    @staticmethod
    def _get_signature_for_diff_chunk(
        diff_chunk: StandardDiffChunk, context_manager: ContextManager
    ) -> Signature:
        """Generate signature and scope information for a single StandardDiffChunk based
        on affected line ranges.

        Args:
            diff_chunk: The StandardDiffChunk to analyze
            context_manager: ContextManager with analysis contexts

        Returns:
            Tuple of (symbols, scope) in the affected line ranges.
            Scope is determined by the LCA scope of the chunk's line ranges.
        """
        languages = set()
        def_old_symbols_acc = set()
        def_new_symbols_acc = set()
        extern_old_symbols_acc = set()
        extern_new_symbols_acc = set()

        new_structural_scopes_acc = set()
        old_structural_scopes_acc = set()

        new_fqns_acc = set()  # Use set for FQNs
        old_fqns_acc = set()  # Use set for FQNs

        def_new_symbols_filtered_acc = set()
        def_old_symbols_filtered_acc = set()
        extern_new_symbols_filtered_acc = set()
        extern_old_symbols_filtered_acc = set()

        if diff_chunk.is_standard_modification or diff_chunk.is_file_rename:
            # For modifications/renames, analyze both old and new line ranges

            # Old version signature
            old_name = diff_chunk.old_file_path.decode("utf-8", errors="replace")
            old_context = context_manager.get_context(
                diff_chunk.old_file_path, diff_chunk.base_hash
            )
            if old_context and diff_chunk.old_start is not None:
                old_end = diff_chunk.old_start + diff_chunk.old_len() - 1
                (
                    def_old_symbols,
                    def_old_symbols_filtered,
                    extern_old_symbols,
                    extern_old_symbols_filtered,
                    old_structural_scopes,
                    old_fqns,
                ) = ContainerLabler._get_signature_for_line_range(
                    diff_chunk.old_start, old_end, old_name, old_context
                )
                languages.add(old_context.detected_language)
                def_old_symbols_acc.update(def_old_symbols)
                def_old_symbols_filtered_acc.update(def_old_symbols_filtered)
                extern_old_symbols_acc.update(extern_old_symbols)
                extern_old_symbols_filtered_acc.update(extern_old_symbols_filtered)
                old_structural_scopes_acc.update(old_structural_scopes)
                old_fqns_acc.update(old_fqns)

            # New version signature
            new_name = diff_chunk.new_file_path.decode("utf-8", errors="replace")
            new_context = context_manager.get_context(
                diff_chunk.new_file_path, diff_chunk.new_hash
            )
            abs_new_start = diff_chunk.get_abs_new_line_start()
            if new_context and abs_new_start is not None:
                abs_new_end = diff_chunk.get_abs_new_line_end() or abs_new_start
                (
                    def_new_symbols,
                    def_new_symbols_filtered,
                    extern_new_symbols,
                    extern_new_symbols_filtered,
                    new_structural_scopes,
                    new_fqns,
                ) = ContainerLabler._get_signature_for_line_range(
                    abs_new_start, abs_new_end, new_name, new_context
                )
                languages.add(new_context.detected_language)
                def_new_symbols_acc.update(def_new_symbols)
                def_new_symbols_filtered_acc.update(def_new_symbols_filtered)
                extern_new_symbols_acc.update(extern_new_symbols)
                extern_new_symbols_filtered_acc.update(extern_new_symbols_filtered)
                new_structural_scopes_acc.update(new_structural_scopes)
                new_fqns_acc.update(new_fqns)

        elif diff_chunk.is_file_addition:
            # For additions, analyze new version only
            new_name = diff_chunk.new_file_path.decode("utf-8", errors="replace")
            new_context = context_manager.get_context(
                diff_chunk.new_file_path, diff_chunk.new_hash
            )
            abs_new_start = diff_chunk.get_abs_new_line_start()
            if new_context and abs_new_start is not None:
                abs_new_end = diff_chunk.get_abs_new_line_end() or abs_new_start
                (
                    def_new_symbols_acc,
                    def_new_symbols_filtered_acc,
                    extern_new_symbols_acc,
                    extern_new_symbols_filtered_acc,
                    new_structural_scopes_acc,
                    new_fqns_acc,
                ) = ContainerLabler._get_signature_for_line_range(
                    abs_new_start, abs_new_end, new_name, new_context
                )
                languages.add(new_context.detected_language)

        elif diff_chunk.is_file_deletion:
            # For deletions, analyze old version only
            old_name = diff_chunk.old_file_path.decode("utf-8", errors="replace")
            old_context = context_manager.get_context(
                diff_chunk.old_file_path, diff_chunk.base_hash
            )
            if old_context and diff_chunk.old_start is not None:
                old_end = diff_chunk.old_start + diff_chunk.old_len() - 1
                (
                    def_old_symbols_acc,
                    def_old_symbols_filtered_acc,
                    extern_old_symbols_acc,
                    extern_old_symbols_filtered_acc,
                    old_structural_scopes_acc,
                    old_fqns_acc,
                ) = ContainerLabler._get_signature_for_line_range(
                    diff_chunk.old_start, old_end, old_name, old_context
                )
                languages.add(old_context.detected_language)

        return Signature(
            file_names=set(diff_chunk.canonical_paths()),
            commit_hashes={diff_chunk.base_hash, diff_chunk.new_hash},
            languages=languages,
            new_structural_scopes=new_structural_scopes_acc,
            old_structural_scopes=old_structural_scopes_acc,
            new_fqns=new_fqns_acc,
            old_fqns=old_fqns_acc,
            def_new_symbols=def_new_symbols_acc,
            def_old_symbols=def_old_symbols_acc,
            extern_new_symbols=extern_new_symbols_acc,
            extern_old_symbols=extern_old_symbols_acc,
            def_new_symbols_filtered=def_new_symbols_filtered_acc,
            def_old_symbols_filtered=def_old_symbols_filtered_acc,
            extern_new_symbols_filtered=extern_new_symbols_filtered_acc,
            extern_old_symbols_filtered=extern_old_symbols_filtered_acc,
        )

    @staticmethod
    def _get_signature_for_line_range(
        start_line: int, end_line: int, file_name: str, context: AnalysisContext
    ) -> tuple[set[str], set[str], set[str], set[str], set[str], set[TypedFQN]]:
        """Get signature and scope information for a specific line range using the
        analysis context.

        Args:
            start_line: Starting line number (1-indexed)
            end_line: Ending line number (1-indexed, inclusive)
            context: AnalysisContext containing symbol map and scope map

        Returns:
            Tuple of (defined symbols, external symbols, structural scopes, fqns) for the specified line range.
            FQNs are constructed by tracking scope changes line-by-line to handle chunks spanning multiple scopes.
        """
        from codestory.core.semantic_analysis.mappers.query_manager import QueryManager
        from codestory.core.semantic_analysis.mappers.scope_mapper import NamedScope

        defined_range_symbols = set()
        defined_range_symbols_filtered = set()
        extern_range_symbols = set()
        extern_range_symbols_filtered = set()
        structural_scopes_range = set()
        fqns: set[TypedFQN] = set()  # Set of TypedFQN objects

        if start_line < 1 or end_line < start_line:
            # Chunks that are pure deletions can fall into this
            return (
                defined_range_symbols,
                defined_range_symbols_filtered,
                extern_range_symbols,
                extern_range_symbols_filtered,
                structural_scopes_range,
                fqns,
            )

        # convert to zero indexed
        start_index = start_line - 1
        end_index = end_line - 1

        # Track scope stack for FQN construction (list of NamedScope objects)
        scope_stack: list[NamedScope] = []
        prev_scopes_list: list[NamedScope] = []
        scopes_added_since_last_save = False

        # Collect symbols from all lines in the range
        for line in range(start_index, end_index + 1):
            # handle scopes

            structural_scopes = context.scope_map.structural_scope_lines.get(line)
            if structural_scopes:
                structural_scopes_range.update(structural_scopes)

            # Get named scopes for this line (already sorted, list of NamedScope)
            current_scopes_list = context.scope_map.semantic_named_scopes.get(line, [])

            # Detect scope changes by comparing lists
            # Find the common prefix length
            common_prefix_len = 0
            for i in range(min(len(prev_scopes_list), len(current_scopes_list))):
                if prev_scopes_list[i] == current_scopes_list[i]:
                    common_prefix_len += 1
                else:
                    break

            # If we lost scopes (current is shorter or diverges), save the current FQN
            if len(prev_scopes_list) > common_prefix_len and scope_stack:
                scope_names = [s.name for s in scope_stack]
                fqn_str = f"{file_name}:{'.'.join(scope_names)}"
                # Type of FQN is the type of the last scope component
                fqn_type = scope_stack[-1].scope_type if scope_stack else "unknown"
                if fqn_str:  # Only add non-empty FQNs
                    fqns.add(TypedFQN(fqn=fqn_str, fqn_type=fqn_type))
                    scopes_added_since_last_save = False  # Reset after saving

            # Update the stack to match current scopes
            # Keep only the common prefix
            scope_stack = list(current_scopes_list[:common_prefix_len])
            newly_defined_scopes = None

            # Add any new scopes from current
            if len(current_scopes_list) > common_prefix_len:
                newly_defined_scopes = current_scopes_list[common_prefix_len:]
                scope_stack.extend(newly_defined_scopes)
                scopes_added_since_last_save = True  # Mark that we added scopes

            prev_scopes_list = current_scopes_list

            # handle symbols

            if newly_defined_scopes:
                newly_defined_scopes_names = [s.name for s in newly_defined_scopes]
            else:
                newly_defined_scopes_names = None

            # we are explicitly removing scopes defined on the same line from appearing as symbols, as this "double counts" them otherwise
            # Symbols explicitly defined on this line
            defined_line_symbols = context.symbol_map.modified_line_symbols.get(line)

            if defined_line_symbols:
                defined_range_symbols.update(defined_line_symbols)

                # filter out defines fqns on this line
                if newly_defined_scopes_names:
                    defined_line_symbols = {
                        symbol
                        for symbol in defined_line_symbols
                        if QueryManager.extract_qualified_symbol_name(symbol)
                        not in newly_defined_scopes_names
                    }

                defined_range_symbols_filtered.update(defined_line_symbols)

            # Symbols referenced on this line but not defined in this file/version
            extern_line_symbols = context.symbol_map.extern_line_symbols.get(line)

            if extern_line_symbols:
                extern_range_symbols.update(extern_line_symbols)

                if newly_defined_scopes_names:
                    extern_line_symbols = {
                        symbol
                        for symbol in extern_line_symbols
                        if QueryManager.extract_qualified_symbol_name(symbol)
                        not in newly_defined_scopes_names
                    }

                extern_range_symbols_filtered.update(extern_line_symbols)

        # At the end, only save if we have a stack AND we've added scopes since the last save
        if scope_stack and scopes_added_since_last_save:
            scope_names = [s.name for s in scope_stack]
            fqn_str = f"{file_name}:{'.'.join(scope_names)}"
            fqn_type = scope_stack[-1].scope_type if scope_stack else "unknown"
            if fqn_str:
                fqns.add(TypedFQN(fqn=fqn_str, fqn_type=fqn_type))

        return (
            defined_range_symbols,
            defined_range_symbols_filtered,
            extern_range_symbols,
            extern_range_symbols_filtered,
            structural_scopes_range,
            fqns,
        )
