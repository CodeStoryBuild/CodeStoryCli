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
from collections.abc import Callable
from dataclasses import dataclass

from codestory.core.data.chunk import Chunk
from codestory.core.data.commit_group import CommitGroup
from codestory.core.data.immutable_chunk import ImmutableChunk
from codestory.core.embeddings.clusterer import Clusterer
from codestory.core.embeddings.embedder import Embedder
from codestory.core.grouper.interface import LogicalGrouper
from codestory.core.llm import CodeStoryAdapter
from codestory.core.semantic_grouper.chunk_lableler import AnnotatedChunk, ChunkLabeler
from codestory.core.semantic_grouper.context_manager import ContextManager
from codestory.core.synthesizer.diff_generator import DiffGenerator
from codestory.core.synthesizer.utils import get_patches_chunk

# -----------------------------------------------------------------------------
# Prompts (Optimized for 1.5B LLMs)
# -----------------------------------------------------------------------------

# 1.5B Model Strategy:
# 1. Use "### Instruction / ### Input / ### Response" delimiters (standard for small models).
# 2. Explicitly define the tone (Imperative mood) to prevent chatting.
# 3. Mention the input format (JSON) so the model doesn't hallucinate plain text.

PROMPT = """### Instruction:
Analyze the following git patch data provided in JSON format. 
Write a single, concise git commit message (under 50 characters) in the imperative mood (e.g., "Fix login bug", "Update user schema").
Focus on the technical change described in 'patch' and 'modified_symbols'.
Do not provide explanations. Output ONLY the commit message.

### Input:
{changes}

### Response:
"""

CLUSTER_SUMMARY_PROMPT = """### Instruction:
You are a Release Manager. Combine the following list of change summaries into a single, cohesive git commit message.

Rules:
1. Synthesize the changes into one sentence.
2. Use imperative mood (e.g., "Refactor authentication", not "Refactored").
3. Do not simply list the items.
4. Output ONLY the final message string.

### Input:
{summaries}

### Response:
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

    def generate_summaries(self, annotated_chunk_patches: list[str]):
        tasks = [PROMPT.format(changes=patch) for patch in annotated_chunk_patches]
        summaries = self.model.invoke_batch(tasks)
        # Added stricter cleanup for small models which often output quotes or newlines
        return [
            summary.strip().strip('"').strip("'").split("\n")[0]
            for summary in summaries
        ]

    def generate_annotated_patches(
        self, annotated_chunks: list[AnnotatedChunk], diff_generator: DiffGenerator
    ) -> list[str]:
        patches = []
        for annotated_chunk in annotated_chunks:
            if annotated_chunk.signature is None:
                patch = self.generate_minimal_patch(
                    annotated_chunk.chunk, diff_generator
                )
            else:
                patch = self.generate_annotated_patch(annotated_chunk, diff_generator)
            patches.append(patch)
        return patches

    def generate_annotated_patch(
        self, annotated_chunk: AnnotatedChunk, diff_generator: DiffGenerator
    ) -> str:
        annotated_patch = []
        for chunk, signature in zip(
            annotated_chunk.chunk.get_chunks(),
            annotated_chunk.signature.signatures,
            strict=True,
        ):
            patch = get_patches_chunk([chunk], diff_generator)[0]  # only one chunk
            modified_symbols = signature.def_old_symbols.intersection(
                signature.def_new_symbols
            )
            added_symbols = signature.def_new_symbols - modified_symbols
            removed_symbols = signature.def_old_symbols - modified_symbols
            # these "fallbacks" where we use other path will never actually occur, as the analysis context would be none
            new_file_name = (chunk.new_file_path or chunk.old_file_path).decode(
                "utf-8", errors="replace"
            )
            old_file_name = (chunk.old_file_path or chunk.new_file_path).decode(
                "utf-8", errors="replace"
            )
            new_fully_qualified_name = ".".join(
                [new_file_name] + signature.new_named_scopes
            )
            old_fully_qualified_name = ".".join(
                [old_file_name] + signature.new_named_scopes
            )

            patch_json = {
                "patch": patch,
                "modified_symbols": list(modified_symbols),
                "added_symbols": list(added_symbols),
                "removed_symbols": list(removed_symbols),
                "new_fully_qualified_name": new_fully_qualified_name,
                "old_fully_qualified_name": old_fully_qualified_name,
            }
            annotated_patch.append(patch_json)
            # Removed print statement to prevent stdout clutter in production
            print(json.dumps(patch_json, indent=2))

        return json.dumps(annotated_patch, indent=2)

    def generate_minimal_patch(
        self, chunk: Chunk, diff_generator: DiffGenerator
    ) -> str:
        patch_json = {
            "patch": get_patches_chunk([chunk], diff_generator)[0],
        }
        return json.dumps(patch_json, indent=2)

    def group_chunks(
        self,
        chunks: list[Chunk],
        immut_chunks: list[ImmutableChunk],
        context_manager: ContextManager,
        message: str,
        on_progress: Callable[[int], None] | None = None,
    ) -> list[CommitGroup]:
        """
        Main entry point.
        """
        if not (chunks or immut_chunks):
            return []

        annotated_chunks = ChunkLabeler.annotate_chunks(chunks, context_manager)
        diff_generator = DiffGenerator(
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
        cluster_labels = self.clusterer.cluster(embeddings).labels_

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

        return groups
