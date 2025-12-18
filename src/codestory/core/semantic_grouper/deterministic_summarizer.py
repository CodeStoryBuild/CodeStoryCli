from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from codestory.core.data.chunk import Chunk
from codestory.core.data.composite_diff_chunk import CompositeDiffChunk
from codestory.core.data.immutable_chunk import ImmutableChunk
from codestory.core.semantic_grouper.chunk_lableler import (
    AnnotatedChunk,
    ChunkSignature,
    Signature,
)

if TYPE_CHECKING:
    from codestory.core.grouper.embedding_grouper import Cluster


class DeterministicSummarizer:
    """
    Generates deterministic, commit-style summaries for code changes.

    Pipeline:
    1. Collect: Gather raw file operations and semantic symbol changes.
    2. Prune: Remove child symbols (methods) if parent (class) is already handled.
    3. Format: readable text with scope compression and smart path shortening.
    """

    # Priority Constants (Lower is higher priority)
    PRIO_RENAME = 0
    PRIO_SEMANTIC = 1  # Adds/Removes/Updates of symbols
    PRIO_FILE_OP = 2  # Generic file Add/Delete

    def __init__(self, max_items: int = 3, compression_threshold: int = 5):
        self.max_items = max_items
        self.compression_threshold = compression_threshold

    def summarize_all(
        self, all_chunks: list[AnnotatedChunk | ImmutableChunk]
    ) -> list[str]:
        """Generate summaries for a mixed list of chunks."""
        summaries = []
        for chunk in all_chunks:
            if isinstance(chunk, AnnotatedChunk):
                summaries.append(self.generate_chunk_summary(chunk))
            else:
                # ImmutableChunk handling
                file_name = self._decode_path(chunk.canonical_path)
                short_name = self._shorten_path(file_name, [file_name])
                diff = chunk.file_patch.decode("utf-8", errors="replace")
                summaries.append(
                    self.generate_immutable_chunk_summary(short_name, diff)
                )
        return summaries

    def summarize_clusters(self, clusters: dict[int, Cluster]) -> dict[int, str]:
        """Generate summaries for clusters of chunks."""
        cluster_messages_map = {}
        for cluster_id, cluster in clusters.items():
            combined_diff_chunks = []
            combined_signatures = []
            immutable_summaries = []

            # Separate annotated vs immutable
            for chunk, summary in zip(cluster.annotated_chunks, cluster.summaries, strict=False):
                if isinstance(chunk, AnnotatedChunk):
                    combined_diff_chunks.extend(chunk.chunk.get_chunks())
                    # Signatures might be None if the chunk wasn't labeled
                    sig = (
                        chunk.signature.signatures
                        if chunk.signature
                        else [None] * len(chunk.chunk.get_chunks())
                    )
                    combined_signatures.extend(sig)
                else:
                    immutable_summaries.append(summary)

            main_summary = ""
            if combined_diff_chunks:
                # Create a composite chunk to summarize the whole group semantically
                dummy_chunk = CompositeDiffChunk(combined_diff_chunks)
                valid_sigs = [s for s in combined_signatures if s is not None]
                total_sig = (
                    Signature.from_signatures(valid_sigs) if valid_sigs else Signature()
                )

                dummy_annotated_chunk = AnnotatedChunk(
                    chunk=dummy_chunk,
                    signature=ChunkSignature(
                        total_signature=total_sig, signatures=combined_signatures
                    ),
                )
                main_summary = self.generate_chunk_summary(dummy_annotated_chunk)

            # Combine semantic summary with immutable summaries (e.g. binary files)
            if immutable_summaries:
                max_immut = 2
                display_immut = immutable_summaries[:max_immut]
                immut_text = ", ".join(display_immut)
                if len(immutable_summaries) > max_immut:
                    immut_text += f" and {len(immutable_summaries) - max_immut} others"

                cluster_messages_map[cluster_id] = (
                    f"{main_summary}; {immut_text}" if main_summary else immut_text
                )
            else:
                cluster_messages_map[cluster_id] = main_summary

        return cluster_messages_map

    def generate_immutable_chunk_summary(self, file_name: str, diff: str) -> str:
        if "--- /dev/null" in diff:
            return f"Add {file_name}"
        if "+++ /dev/null" in diff:
            return f"Delete {file_name}"
        return f"Update {file_name}"

    def generate_chunk_summary(self, annotated_chunk: AnnotatedChunk) -> str:
        """Entry point for summarizing a chunk with potential semantic data."""
        if (
            annotated_chunk.signature is None
            or not annotated_chunk.signature.signatures
        ):
            return self._summarize_raw_diffs(annotated_chunk.chunk)

        return self._summarize_semantically(annotated_chunk)

    # -------------------------------------------------------------------------
    # Pipeline Stages
    # -------------------------------------------------------------------------

    def _summarize_raw_diffs(self, chunk: Chunk) -> str:
        """Fallback: lists file operations when no semantic signatures exist."""
        diff_chunks = chunk.get_chunks()
        if not diff_chunks:
            return "Modify files"

        all_paths = [self._decode_path(dc.canonical_path()) for dc in diff_chunks]
        actions = []

        for dc, raw_path in zip(diff_chunks, all_paths, strict=False):
            short_path = self._shorten_path(raw_path, all_paths)

            if dc.is_file_rename:
                old = self._decode_path(dc.old_file_path)
                old_short = self._shorten_path(old, [old])
                actions.append(
                    {
                        "msg": f"Rename {old_short} to {short_path}",
                        "prio": self.PRIO_RENAME,
                        "len": len(short_path),
                    }
                )
            elif dc.is_file_addition:
                actions.append(
                    {
                        "msg": f"Add {short_path}",
                        "prio": self.PRIO_FILE_OP,
                        "len": len(short_path),
                    }
                )
            elif dc.is_file_deletion:
                actions.append(
                    {
                        "msg": f"Delete {short_path}",
                        "prio": self.PRIO_FILE_OP,
                        "len": len(short_path),
                    }
                )
            else:
                actions.append(
                    {
                        "msg": f"Update {short_path}",
                        "prio": self.PRIO_SEMANTIC,
                        "len": len(short_path),
                    }
                )

        return self._rank_and_join(actions)

    def _summarize_semantically(self, annotated_chunk: AnnotatedChunk) -> str:
        """Main pipeline for semantic summarization."""

        # 1. Collect
        file_ops, symbol_buckets, active_files_map = self._collect_changes(
            annotated_chunk
        )

        # 2. Prune
        self._prune_hierarchies(symbol_buckets)

        # 3. Format
        return self._format_semantic_summary(file_ops, symbol_buckets, active_files_map)

    def _collect_changes(self, annotated_chunk: AnnotatedChunk):
        """
        Parses diff chunks and signatures into generic file ops and symbol buckets.
        Returns:
            file_ops: List of generic actions (renames, raw adds).
            symbol_buckets: Dict[verb, Dict[filepath, set[symbols]]].
            active_files_map: Dict[filepath, bool] (bool indicates if symbols were found).
        """
        diff_chunks = annotated_chunk.chunk.get_chunks()
        signatures = annotated_chunk.signature.signatures

        # If mismatch, we can't align semantics to files, usually implies data issue
        if len(diff_chunks) != len(signatures):
            return [], {}, {}

        file_ops = []
        symbol_buckets = {
            "Add": defaultdict(set),
            "Remove": defaultdict(set),
            "Update": defaultdict(set),
        }
        active_files_map = {}

        for dc, sig in zip(diff_chunks, signatures, strict=False):
            path_str = self._decode_path(dc.canonical_path())
            has_symbols = sig and (sig.new_fqns or sig.old_fqns or sig.def_new_symbols)
            active_files_map[path_str] = has_symbols

            # -- File Operations --
            if dc.is_file_rename:
                old = self._decode_path(dc.old_file_path)
                file_ops.append(
                    {
                        "type": "rename",
                        "old": old,
                        "new": path_str,
                        "prio": self.PRIO_RENAME,
                    }
                )
                # Fall through to process symbols inside the renamed file
            elif dc.is_file_addition:
                # OPTIMIZATION: If we found symbols, we suppress the generic "Add file.py"
                # to focus on "Add ClassFoo".
                if not has_symbols:
                    file_ops.append(
                        {"type": "add", "path": path_str, "prio": self.PRIO_FILE_OP}
                    )
            elif dc.is_file_deletion:
                file_ops.append(
                    {"type": "delete", "path": path_str, "prio": self.PRIO_FILE_OP}
                )
                # No symbols to process on deletion usually
                continue

            if not sig:
                continue

            # -- Symbol Bucketization --
            for fqn in sig.new_fqns - sig.old_fqns:
                self._bucket_fqn(fqn, symbol_buckets["Add"], path_str)
            for fqn in sig.old_fqns - sig.new_fqns:
                self._bucket_fqn(fqn, symbol_buckets["Remove"], path_str)
            for fqn in sig.new_fqns & sig.old_fqns:
                self._bucket_fqn(fqn, symbol_buckets["Update"], path_str)

        return file_ops, symbol_buckets, active_files_map

    def _prune_hierarchies(self, buckets: dict[str, dict[str, set[str]]]):
        """
        Removes child symbols if the parent is present.
        """
        adds = buckets["Add"]
        removes = buckets["Remove"]
        updates = buckets["Update"]

        # Helper to prune a single set of symbols
        def get_roots(symbols: set[str]) -> set[str]:
            sorted_syms = sorted(list(symbols))
            roots = set()
            for sym in sorted_syms:
                # Check if this symbol is a child of any existing root
                # e.g., "Class.method" starts with "Class."
                if any(
                    sym.startswith(r + ".") or sym.startswith(r + ":") for r in roots
                ):
                    continue
                roots.add(sym)
            return roots

        # 1. Internal Pruning (within same verb)
        for f in adds:
            adds[f] = get_roots(adds[f])
        for f in removes:
            removes[f] = get_roots(removes[f])
        for f in updates:
            updates[f] = get_roots(updates[f])

        # 2. Cross-Verb Pruning
        # If a Class is in "Update", any "Add Method" for that class is just a detail.
        for f, update_roots in updates.items():
            if not update_roots:
                continue

            if f in adds:
                adds[f] = {
                    s
                    for s in adds[f]
                    if not any(s.startswith(u + ".") for u in update_roots)
                }
            if f in removes:
                removes[f] = {
                    s
                    for s in removes[f]
                    if not any(s.startswith(u + ".") for u in update_roots)
                }

    def _format_semantic_summary(self, file_ops, symbol_buckets, active_files_map):
        """Converts pruned data into human readable messages."""
        all_paths_list = list(active_files_map.keys())
        messages = []

        # 1. Format File Ops
        for op in file_ops:
            if op["type"] == "rename":
                old_s = self._shorten_path(op["old"], [op["old"]])
                new_s = self._shorten_path(op["new"], all_paths_list)
                messages.append(
                    {"msg": f"Rename {old_s} to {new_s}", "prio": op["prio"], "len": 15}
                )
            elif op["type"] == "add":
                path_s = self._shorten_path(op["path"], all_paths_list)
                messages.append(
                    {"msg": f"Add {path_s}", "prio": op["prio"], "len": len(path_s)}
                )
            elif op["type"] == "delete":
                path_s = self._shorten_path(op["path"], all_paths_list)
                messages.append(
                    {"msg": f"Delete {path_s}", "prio": op["prio"], "len": len(path_s)}
                )

        # 2. Format Symbols
        def process_bucket(verb: str, priority: int):
            bucket = symbol_buckets.get(verb, {})
            for file_path, symbols in bucket.items():
                if not symbols:
                    continue

                short_file = self._shorten_path(file_path, all_paths_list)

                # Compression: "Update 12 symbols in foo.py"
                if len(symbols) > self.compression_threshold:
                    msg = f"{verb} {len(symbols)} symbols in {short_file}"
                    messages.append({"msg": msg, "prio": priority, "len": 100})
                else:
                    sorted_syms = sorted(list(symbols), key=len, reverse=True)
                    joined = ", ".join(sorted_syms)

                    # Context Decision
                    # If only 1 file is involved globally, we can omit the filename.
                    # Otherwise, we ALWAYS include it for clarity.
                    if len(active_files_map) == 1:
                        text = f"{verb} {joined}"
                    else:
                        text = f"{verb} {joined} in {short_file}"

                    messages.append(
                        {
                            "msg": text,
                            "prio": priority,
                            "len": sum(len(s) for s in symbols),
                        }
                    )

        # All semantic changes share equal high priority (PRIO_SEMANTIC = 1)
        process_bucket("Add", self.PRIO_SEMANTIC)
        process_bucket("Remove", self.PRIO_SEMANTIC)
        process_bucket("Update", self.PRIO_SEMANTIC)

        # Fallback: if we touched files but produced zero messages
        # (e.g. only updates that were filtered out or empty signatures), generic fallback.
        if not messages and active_files_map:
            prefix = self._get_shared_prefix(all_paths_list)
            fallback = f"Update files in {prefix}" if prefix else "Update files"
            return fallback

        return self._rank_and_join(messages)

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------

    def _bucket_fqn(self, fqn: str, bucket: dict[str, set[str]], fallback_file: str):
        """Helpers to parse 'File:Symbol' or 'Symbol' strings."""
        head, sep, tail = fqn.partition(":")
        if sep:
            bucket[head].add(tail)
        else:
            bucket[fallback_file].add(fqn)

    def _rank_and_join(self, actions: list[dict[str, Any]]) -> str:
        """
        Sorts actions by Priority (asc) then Significance/Length (desc).
        Deduplicates and joins with semicolons.
        """
        sorted_actions = sorted(actions, key=lambda x: (x["prio"], -x["len"]))

        final_msgs = [x["msg"] for x in sorted_actions]
        # Preserve order while removing duplicates
        unique = list(dict.fromkeys(final_msgs))

        if not unique:
            return ""

        if len(unique) <= self.max_items:
            return "; ".join(unique)

        return (
            "; ".join(unique[: self.max_items])
            + f" and {len(unique) - self.max_items} others"
        )

    def _shorten_path(self, target: str, context: list[str]) -> str:
        """
        Shortens 'path/to/foo.py' to 'foo.py'.
        If 'foo.py' is ambiguous in the provided context, keeps parent folders until unique.
        """
        if not target:
            return ""

        target_parts = target.split("/")
        candidate = target_parts[-1]

        # Check for ambiguity (same filename in different folders)
        collision = False
        for other in context:
            if other == target:
                continue
            other_filename = other.split("/")[-1]
            if other_filename == candidate:
                collision = True
                break

        if not collision:
            return candidate

        # If collision, try adding parent (e.g., 'utils/foo.py')
        if len(target_parts) > 1:
            return f"{target_parts[-2]}/{target_parts[-1]}"

        return target

    def _get_shared_prefix(self, scopes: list[str]) -> str:
        if not scopes:
            return ""
        if len(scopes) == 1:
            return self._shorten_path(scopes[0], scopes)

        split_paths = [s.split("/") for s in scopes]
        common_parts = []
        for parts in zip(*split_paths, strict=False):
            if len(set(parts)) == 1:
                common_parts.append(parts[0])
            else:
                break

        if common_parts:
            return "/".join(common_parts)

        return ""  # No common prefix

    def _decode_path(self, path: bytes | None) -> str:
        if path is None:
            return "unknown"
        return path.decode("utf-8", errors="replace")
