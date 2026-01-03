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

# -----------------------------------------------------------------------------
# codestory - Dual Licensed Software
# Copyright (c) 2025 Adem Can
# -----------------------------------------------------------------------------

import json
from dataclasses import dataclass

from loguru import logger

from codestory.core.data.chunk import Chunk
from codestory.core.data.commit_group import CommitGroup
from codestory.core.data.immutable_chunk import ImmutableChunk
from codestory.core.diff_generation.diff_generator import DiffGenerator
from codestory.core.diff_generation.semantic_diff_generator import SemanticDiffGenerator
from codestory.core.embeddings.clusterer import Clusterer
from codestory.core.embeddings.embedder import Embedder
from codestory.core.grouper.interface import LogicalGrouper
from codestory.core.llm import CodeStoryAdapter
from codestory.core.semantic_grouper.chunk_lableler import AnnotatedChunk, ChunkLabeler
from codestory.core.semantic_grouper.context_manager import ContextManager

# -----------------------------------------------------------------------------
# Prompts (Optimized for 1.5B LLMs)
# -----------------------------------------------------------------------------

# 1.5B Model Strategy:
# 1. Use "### Instruction / ### Input / ### Response" delimiters (standard for small models).
# 2. Explicitly define the tone (Imperative mood) to prevent chatting.
# 3. Mention the input format (JSON) so the model doesn't hallucinate plain text.

INITIAL_SUMMARY_PROMPT = """
### Task:
You are a specialized function that converts structured code change data into a concise Git commit message.

**Input:**
- `git_patch` and JSON metadata (added_symbols, removed_symbols, etc.)
- Focus only on *visible code changes*.

**Rules:**
1. Output a single-line commit message, max 72 characters.
2. Use imperative mood: e.g., "Add", "Remove", "Update", "Refactor".
3. Describe what changed and where (file/module/class/function) using the data.
4. Do NOT include inferred goals, benefits, or context.
5. Output ONLY the message, nothing else.

**Changes:**
{changes}

**Commit Message:**
"""


CLUSTER_SUMMARY_PROMPT = """
### Task:
You are a Git commit message generator. Your goal is to create a single cohesive commit message subject line from multiple commit summaries.

**Input:**
- A list of change summaries (`summaries`)

**Rules:**
1. Output a single-line message, max 72 characters.
2. Use imperative mood (e.g., "Refactor", "Add", "Remove", "Update").
3. Include all core technical actions and primary locations (files/modules).
4. Do NOT add inferred goals, benefits, or justifications.
5. Output ONLY the final message string.

**Commit Summaries:**
{summaries}

**Final Commit Message:**
"""


@dataclass
class Cluster:
    chunks: list[Chunk | ImmutableChunk]
    summaries: list[str]


class EmbeddingGrouper(LogicalGrouper):
    def __init__(self, model: CodeStoryAdapter):
        self.model = model
        self.embedder = Embedder()
        self.clusterer = Clusterer()
        self.patch_cutoff_chars = 1000

    def generate_summaries(self, annotated_chunk_patches: list[str]):
        tasks = [
            INITIAL_SUMMARY_PROMPT.format(changes=patch)
            for patch in annotated_chunk_patches
        ]
        logger.debug(f"Generating {len(tasks)} summaries using LLM.")
        summaries = self.model.invoke_batch(tasks)
        # Added stricter cleanup for small models which often output quotes or newlines
        return [summary.strip().strip('"').strip("'") for summary in summaries]

    def generate_annotated_patches(
        self, annotated_chunks: list[AnnotatedChunk], diff_generator: DiffGenerator
    ) -> list[str]:
        patches = []
        for annotated_chunk in annotated_chunks:
            patch = self.generate_annotated_patch(annotated_chunk, diff_generator)
            patches.append(patch)
        return patches

    def generate_annotated_patch(
        self, annotated_chunk: AnnotatedChunk, diff_generator: DiffGenerator
    ) -> str:
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
            # we get diff generator [0] since we pass only one chunk, then we cut off to limit size
            patch = diff_generator.get_patch(chunk)[: self.patch_cutoff_chars]
            patch_json = {}

            patch_json["git_patch"] = patch

            # add only relevant info
            if signature is not None:
                # remove extra symbol info for cleaner output
                # eg "foo identifier_class python" -> "foo"
                new_symbols_cleaned = {
                    sym.partition(" ")[0] for sym in signature.def_new_symbols
                }
                old_symbols_cleaned = {
                    sym.partition(" ")[0] for sym in signature.def_old_symbols
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
                    patch_json["affected_scopes"] = list(
                        signature.new_fqns | signature.old_fqns
                    )

            annotated_patch.append(patch_json)

        return json.dumps(annotated_patch, indent=2)

    def group_chunks(
        self,
        chunks: list[Chunk],
        immut_chunks: list[ImmutableChunk],
        context_manager: ContextManager,
        message: str,
    ) -> list[CommitGroup]:
        """
        Main entry point.
        """
        if not (chunks or immut_chunks):
            return []

        annotated_chunks = ChunkLabeler.annotate_chunks(chunks, context_manager)
        diff_generator = SemanticDiffGenerator(
            chunks
        )  # immutable chunks wont be used for total patch calcs

        annotated_chunk_patches = self.generate_annotated_patches(
            annotated_chunks, diff_generator
        )
        # add in immutable chunks (they have no annotated chunk "capablities")
        immut_patches = [immut.file_patch[:200] for immut in immut_chunks]

        all_patch_data = annotated_chunk_patches + immut_patches
        all_chunks_reference = chunks + immut_chunks

        summaries = self.generate_summaries(all_patch_data)

        if len(all_chunks_reference) == 1:
            # no clustering, just one commit group
            return [
                CommitGroup(
                    chunks=[all_chunks_reference[0]],
                    commit_message=summaries[0],
                )
            ]
        embeddings = self.embedder.embed(summaries)
        cluster_labels = self.clusterer.cluster(embeddings)

        groups = []
        clusters = {}

        # Build clusters: group chunks and their summaries by cluster label
        for any_chunk, summary, cluster_label in zip(
            all_chunks_reference, summaries, cluster_labels, strict=True
        ):
            if cluster_label == -1:
                # noise, assign as its own group. Reuse summary as group message
                group = CommitGroup(
                    chunks=[any_chunk],
                    commit_message=summary,
                )
                groups.append(group)
            else:
                if cluster_label not in clusters:
                    clusters[cluster_label] = Cluster(chunks=[], summaries=[])
                clusters[cluster_label].chunks.append(any_chunk)
                clusters[cluster_label].summaries.append(summary)

        # Generate final commit messages for each cluster
        cluster_summary_tasks = []
        cluster_ids = []
        for cluster_label, cluster in clusters.items():
            summaries_text = "\n".join(f"- {s}" for s in cluster.summaries)
            cluster_summary_tasks.append(
                CLUSTER_SUMMARY_PROMPT.format(summaries=summaries_text)
            )
            cluster_ids.append(cluster_label)

        if cluster_summary_tasks:
            cluster_messages = self.model.invoke_batch(cluster_summary_tasks)

            # Create commit groups from clusters
            for cluster_id, commit_message in zip(
                cluster_ids, cluster_messages, strict=True
            ):
                cluster = clusters[cluster_id]

                # Extra cleanup for cluster messages
                clean_message = commit_message.strip().strip('"').strip("'")

                group = CommitGroup(
                    chunks=cluster.chunks,
                    commit_message=clean_message,
                )
                groups.append(group)

        logger.info(
            f"Created {len(groups)} commit groups from {len(chunks) + len(immut_chunks)} semantic groups using embeddings."
        )

        return groups
