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
from typing import Literal

from loguru import logger

from codestory.core.data.chunk import Chunk
from codestory.core.data.commit_group import CommitGroup
from codestory.core.data.immutable_chunk import ImmutableChunk
from codestory.core.diff_generation.diff_generator import DiffGenerator
from codestory.core.diff_generation.semantic_diff_generator import SemanticDiffGenerator
from codestory.core.embeddings.clusterer import Clusterer
from codestory.core.embeddings.embedder import Embedder
from codestory.core.exceptions import LLMResponseError
from codestory.core.grouper.interface import LogicalGrouper
from codestory.core.llm import CodeStoryAdapter
from codestory.core.semantic_grouper.chunk_lableler import AnnotatedChunk, ChunkLabeler
from codestory.core.semantic_grouper.context_manager import ContextManager

# -----------------------------------------------------------------------------
# Prompts (Optimized for 1.5B LLMs)
# -----------------------------------------------------------------------------

INITIAL_SUMMARY_SYSTEM = """You are a specialized function that converts structured code change data into a concise Git commit message.

**Input:**
- `git_patch` and JSON metadata (added_symbols, removed_symbols, etc.)
- Focus only on *visible code changes*.

**Rules:**
1. Output a single-line commit message, max 72 characters.
2. Use imperative mood: e.g., "Add", "Remove", "Update", "Refactor".
3. Describe what changed and where (file/module/class/function) using the data.
4. Do NOT include inferred goals, benefits, or context.
5. Output ONLY the message, nothing else."""

INITIAL_SUMMARY_USER = """**Changes:**
{changes}

**Commit Message:**"""


CLUSTER_SUMMARY_SYSTEM = """You are a Git commit message generator. Your goal is to create a single cohesive commit message subject line from multiple commit summaries.

**Input:**
- A list of change summaries (`summaries`)

**Rules:**
1. Output a single-line message, max 72 characters.
2. Use imperative mood (e.g., "Refactor", "Add", "Remove", "Update").
3. Include all core technical actions and primary locations (files/modules).
4. Do NOT add inferred goals, benefits, or justifications.
5. Output ONLY the final message string."""

CLUSTER_SUMMARY_USER = """**Commit Summaries:**
{summaries}

**Final Commit Message:**"""


BATCHED_SUMMARY_SYSTEM = """You are a specialized function that converts structured code change data into concise Git commit messages.

**Input:**
- A list of `git_patch` and JSON metadata (added_symbols, removed_symbols, etc.)
- Focus only on *visible code changes*.

**Rules:**
1. Output a JSON list of strings.
2. Each string must be a single-line commit message, max 72 characters.
3. Use imperative mood: e.g., "Add", "Remove", "Update", "Refactor".
4. Describe what changed and where (file/module/class/function) using the data.
5. Do NOT include inferred goals, benefits, or context.
6. The order of the output list must match the order of the input list."""

BATCHED_SUMMARY_USER = """**Changes:**
{changes}

**Output:**"""


@dataclass
class Cluster:
    chunks: list[Chunk | ImmutableChunk]
    summaries: list[str]


@dataclass
class SummaryTask:
    prompt: str
    is_multiple: bool
    indices: list[int]
    original_patches: list[str]


class EmbeddingGrouper(LogicalGrouper):
    def __init__(
        self,
        model: CodeStoryAdapter,
        batching_strategy: Literal["auto", "requests", "prompt"] = "auto",
        max_tokens: int = 4096,
    ):
        self.model = model
        self.batching_strategy = batching_strategy
        self.embedder = Embedder()
        self.clusterer = Clusterer()
        self.patch_cutoff_chars = 1000
        self.max_tokens = max_tokens

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count based on 3 chars per token."""
        return len(text) // 3

    def _partition_patches(
        self, annotated_chunk_patches: list[str], strategy: str
    ) -> list[list[tuple[int, str]]]:
        """
        Partitions patches into groups.
        If strategy is 'requests', every group has size 1.
        If strategy is 'prompt', groups are filled up to max_tokens.
        Returns: List of groups, where each group is a list of (original_index, patch_string)
        """
        partitions = []

        # If requests, simple 1-to-1 mapping
        if strategy == "requests":
            for i, patch in enumerate(annotated_chunk_patches):
                partitions.append([(i, patch)])
            return partitions

        # Strategy == "prompt": Windowing logic
        current_batch = []
        # Calculate base overhead of the prompt template once
        base_prompt_cost = self._estimate_tokens(
            BATCHED_SUMMARY_SYSTEM
        ) + self._estimate_tokens(BATCHED_SUMMARY_USER)
        current_tokens = base_prompt_cost

        for i, patch in enumerate(annotated_chunk_patches):
            # Calculate formatting overhead for this specific item
            # We construct the string we actually inject to measure it accurately
            formatted_patch_overhead = f"--- Change {i + 1} ---\n\n\n"

            patch_cost = self._estimate_tokens(patch) + self._estimate_tokens(
                formatted_patch_overhead
            )

            # Check if adding this patch blows the window
            # If the batch is not empty and adding this exceeds limit, seal the batch
            if current_batch and (current_tokens + patch_cost > self.max_tokens):
                partitions.append(current_batch)
                current_batch = []
                current_tokens = base_prompt_cost

            # Add to current
            current_batch.append((i, patch))
            current_tokens += patch_cost

        if current_batch:
            partitions.append(current_batch)

        return partitions

    def _create_summary_tasks(
        self, partitions: list[list[tuple[int, str]]]
    ) -> list[SummaryTask]:
        """
        Converts partitions of patches into actionable LLM Tasks.
        """
        tasks = []
        for group in partitions:
            indices = [item[0] for item in group]
            patches = [item[1] for item in group]

            if len(group) == 1:
                # Single Request Task
                prompt = INITIAL_SUMMARY_USER.format(changes=patches[0])
                tasks.append(
                    SummaryTask(
                        prompt=prompt,
                        is_multiple=False,
                        indices=indices,
                        original_patches=patches,
                    )
                )
            else:
                # Batched Request Task
                formatted_changes = []
                for i, patch in enumerate(patches):
                    # We use 1-based indexing for the prompt presentation
                    formatted_changes.append(f"--- Change {i + 1} ---\n{patch}")

                combined_changes = "\n\n".join(formatted_changes)
                prompt = BATCHED_SUMMARY_USER.format(changes=combined_changes)
                tasks.append(
                    SummaryTask(
                        prompt=prompt,
                        is_multiple=True,
                        indices=indices,
                        original_patches=patches,
                    )
                )
        return tasks

    def generate_summaries(self, annotated_chunk_patches: list[str]) -> list[str]:
        if not annotated_chunk_patches:
            return []

        strategy = self.batching_strategy
        if strategy == "auto":
            strategy = "requests" if self.model.is_local() else "prompt"

        # 1. Partition based on strategy and window size
        partitions = self._partition_patches(annotated_chunk_patches, strategy)

        # 2. Create Tasks
        tasks = self._create_summary_tasks(partitions)

        logger.info(
            f"Generating summaries for {len(annotated_chunk_patches)} changes (Strategy: {strategy})."
        )

        # 3. Invoke Batch
        messages_list = [
            [
                {
                    "role": "system",
                    "content": BATCHED_SUMMARY_SYSTEM
                    if t.is_multiple
                    else INITIAL_SUMMARY_SYSTEM,
                },
                {"role": "user", "content": t.prompt},
            ]
            for t in tasks
        ]
        responses = self.model.invoke_batch(messages_list)

        # 4. Process Results
        # We pre-allocate the result list to maintain order
        final_summaries = [""] * len(annotated_chunk_patches)

        for task, response in zip(tasks, responses, strict=True):
            if not task.is_multiple:
                # Single task: simple cleanup
                clean_res = response.strip().strip('"').strip("'")
                final_summaries[task.indices[0]] = clean_res
            else:
                # Multi task: Strict JSON parsing
                # Find JSON list syntax
                l_indx = response.find("[")
                r_indx = response.rfind("]")

                if l_indx == -1 or r_indx == -1:
                    logger.error(
                        "Failed to parse batch summary: No JSON list found in LLM response."
                    )
                    raise LLMResponseError("No JSON list found in response")

                clean_response = response[l_indx : r_indx + 1]

                try:
                    batch_summaries = json.loads(clean_response)
                except json.JSONDecodeError as e:
                    logger.error(
                        f"Failed to decode JSON from batch summary response: {e}"
                    )
                    raise LLMResponseError(
                        "Failed to decode JSON from batch summary"
                    ) from e

                if not isinstance(batch_summaries, list):
                    logger.error("Batch summary response is not a list.")
                    raise LLMResponseError("Response is not a list")

                # TODO add more and nicer robustness for model outputs
                batch_summaries = [str(s) for s in batch_summaries if s.strip()]

                if len(batch_summaries) != len(task.indices):
                    logger.error(
                        f"Summary count mismatch: Expected {len(task.indices)}, got {len(batch_summaries)}."
                    )
                    raise LLMResponseError("Batch summary count mismatch")

                # Distribute results
                for idx, summary in zip(task.indices, batch_summaries, strict=True):
                    final_summaries[idx] = str(summary).strip().strip('"').strip("'")

        return final_summaries

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
                [
                    {"role": "system", "content": CLUSTER_SUMMARY_SYSTEM},
                    {
                        "role": "user",
                        "content": CLUSTER_SUMMARY_USER.format(
                            summaries=summaries_text
                        ),
                    },
                ]
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
            f"Organized {len(chunks) + len(immut_chunks)} changes into {len(groups)} logical groups."
        )

        return groups
