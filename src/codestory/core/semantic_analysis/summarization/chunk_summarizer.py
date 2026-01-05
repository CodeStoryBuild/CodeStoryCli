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
"""Chunk summarizer for generating commit message summaries from code chunks."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from codestory.core.diff.data.atomic_container import AtomicContainer
from codestory.core.diff.patch.patch_generator import PatchGenerator
from codestory.core.exceptions import LLMResponseError
from codestory.core.logging.progress_manager import ProgressBarManager
from codestory.core.semantic_analysis.annotation.utils import sanitize_llm_text
from codestory.core.semantic_analysis.summarization.prompts import (
    BATCHED_CLUSTER_FROM_DESCRIPTIVE_SUMMARY_SYSTEM,
    BATCHED_CLUSTER_FROM_DESCRIPTIVE_SUMMARY_USER,
    BATCHED_CLUSTER_SUMMARY_SYSTEM,
    BATCHED_CLUSTER_SUMMARY_USER,
    BATCHED_DESCRIPTIVE_SUMMARY_SYSTEM,
    BATCHED_SUMMARY_SYSTEM,
    BATCHED_SUMMARY_USER,
    CLUSTER_FROM_DESCRIPTIVE_SUMMARY_SYSTEM,
    CLUSTER_SUMMARY_SYSTEM,
    CLUSTER_SUMMARY_USER,
    INITIAL_DESCRIPTIVE_SUMMARY_SYSTEM,
    INITIAL_SUMMARY_SYSTEM,
    INITIAL_SUMMARY_USER,
)
from codestory.core.semantic_analysis.summarization.summarizer_utils import (
    generate_annotated_patch,
)

if TYPE_CHECKING:
    from codestory.core.llm import CodeStoryAdapter
    from codestory.core.semantic_analysis.annotation.context_manager import (
        ContextManager,
    )


@dataclass
class SummaryTask:
    """Represents a task for generating summaries from patches."""

    prompt: str
    is_multiple: bool
    indices: list[int]
    prompt: str
    is_multiple: bool
    indices: list[int]
    original_patches: list[str]
    output_style: Literal["brief", "descriptive"]


@dataclass
class ClusterSummaryTask:
    """Represents a task for generating combined summaries from clusters."""

    prompt: str
    is_multiple: bool
    cluster_ids: list[int]
    prompt: str
    is_multiple: bool
    cluster_ids: list[int]
    summaries_groups: list[list[str]]
    source_style: Literal["brief", "descriptive"]


class ContainerSummarizer:
    """Generates commit message summaries from code chunks.

    Supports batching strategies for efficient LLM usage:
    - 'auto': Automatically selects strategy based on model locality
    - 'requests': One request per chunk (better for local models)
    - 'prompt': Batch multiple chunks per request (better for remote APIs)
    """

    def __init__(
        self,
        codestory_adapter: CodeStoryAdapter,
        context_manager: ContextManager,
        patch_generator: PatchGenerator,
        batching_strategy: Literal["auto", "requests", "prompt"] = "auto",
        max_tokens: int = 32000,
    ):
        """Initialize the ChunkSummarizer.

        Args:
            codestory_adapter: The CodeStoryAdapter for LLM invocation
            batching_strategy: Strategy for batching LLM requests
            max_tokens: Maximum tokens per request
        """
        self.model = codestory_adapter
        self.context_manager = context_manager
        self.patch_generator = patch_generator
        self.batching_strategy = batching_strategy
        self.max_tokens = max_tokens

    def summarize_containers(
        self,
        containers: list[AtomicContainer],
        user_message: str | None = None,
        output_style: Literal["brief", "descriptive"] = "brief",
    ) -> list[str]:
        """Generate summaries for a list of chunks.

        Args:
            chunks: List of Chunk or ImmutableDiffChunk objects
            context_manager: ContextManager for semantic analysis
            patch_generator: DiffGenerator for patch generation
            intent_message: Optional user-provided intent message

        Returns:
            List of summary strings, one per chunk
        """
        if not containers:
            return []

        # Generate annotated patches for all chunks
        annotated_patches = []
        for container in containers:
            patch = generate_annotated_patch(
                container=container,
                context_manager=self.context_manager,
                patch_generator=self.patch_generator,
                max_tokens=self.max_tokens,
            )
            annotated_patches.append(patch)

        # Generate summaries from patches
        # Generate summaries from patches
        formatted_intent = self._create_user_guidance_message(user_message)
        return self._generate_summaries(
            annotated_patches, formatted_intent, output_style
        )

    def summarize_container(
        self,
        container: AtomicContainer,
        context_manager: ContextManager,
        patch_generator: PatchGenerator,
        user_message: str | None = None,
        output_style: Literal["brief", "descriptive"] = "brief",
    ) -> str:
        """Generate a summary for a single container.

        Args:
            chunk: A Chunk or ImmutableDiffChunk object
            context_manager: ContextManager for semantic analysis
            patch_generator: DiffGenerator for patch generation
            intent_message: Optional user-provided intent message

        Returns:
            Summary string for the chunk
        """
        summaries = self.summarize_containers(
            containers=[container],
            user_message=user_message,
            output_style=output_style,
        )
        return summaries[0]

    def _create_user_guidance_message(self, intent_message: str | None) -> str:
        """Format the intent message for inclusion in prompts."""
        if intent_message is None:
            return ""

        return f"\nThe user has provided additional information about the global intent of all their changes. If relevant you should use this information to enhance your summaries\nBEGIN INTENT\n{intent_message}\nEND INTENT\n"

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count based on 3 chars per token."""
        return len(text) // 3

    def _partition_items(
        self,
        items: list[Any],
        item_cost_fn: Callable[[Any], int],
        base_prompt_cost: int,
        strategy: str,
    ) -> list[list[Any]]:
        """Generic partitioner for batching items based on token cost."""
        partitions = []

        if strategy == "requests":
            for item in items:
                partitions.append([item])
            return partitions

        current_batch = []
        current_tokens = base_prompt_cost

        for item in items:
            cost = item_cost_fn(item)

            if current_batch and (current_tokens + cost > self.max_tokens):
                partitions.append(current_batch)
                current_batch = []
                current_tokens = base_prompt_cost

            current_batch.append(item)
            current_tokens += cost

        if current_batch:
            partitions.append(current_batch)

        return partitions

    def _parse_markdown_list_response(
        self, response: str, expected_count: int
    ) -> list[str]:
        """Parses a numbered markdown list response from the LLM.

        Expects format:
        1. First item
        2. Second item
        ...
        """
        # Match numbered list items: "1. content", "2. content", etc.
        pattern = r"^\s*(\d+)\.\s+(.+)$"
        items = []

        for line in response.strip().split("\n"):
            match = re.match(pattern, line.strip())
            if match:
                items.append(match.group(2).strip())

        if len(items) != expected_count:
            raise LLMResponseError(
                f"List count mismatch: Expected {expected_count}, got {len(items)}"
            )

        return items

    def _partition_patches(
        self,
        annotated_chunk_patches: list[str],
        strategy: str,
        intent_message: str,
    ) -> list[list[tuple[int, str]]]:
        """Partitions patches into groups.

        If strategy is 'requests', every group has size 1.
        If strategy is 'prompt', groups are filled up to max_tokens.
        Returns: List of groups, where each group is a list of (original_index, patch_markdown)
        """
        base_prompt_cost = self._estimate_tokens(
            BATCHED_SUMMARY_SYSTEM.format(message=intent_message)
        ) + self._estimate_tokens(BATCHED_SUMMARY_USER)

        items = list(enumerate(annotated_chunk_patches))

        def cost_fn(item: tuple[int, str]) -> int:
            i, patch_md = item
            # Overhead for change header in batched prompt
            header_overhead = f"### Change {i + 1}\n"
            return self._estimate_tokens(patch_md) + self._estimate_tokens(
                header_overhead
            )

        return self._partition_items(items, cost_fn, base_prompt_cost, strategy)

    def _create_summary_tasks(
        self,
        partitions: list[list[tuple[int, str]]],
        output_style: Literal["brief", "descriptive"],
    ) -> list[SummaryTask]:
        """Converts partitions of patches into actionable LLM Tasks.

        Patches are now markdown strings.
        """
        tasks = []
        for group in partitions:
            indices = [item[0] for item in group]
            patches = [item[1] for item in group]

            if len(group) == 1:
                # Single Request Task - use patch markdown directly
                prompt = INITIAL_SUMMARY_USER.format(changes=patches[0])
                tasks.append(
                    SummaryTask(
                        prompt=prompt,
                        is_multiple=False,
                        indices=indices,
                        original_patches=patches,
                        output_style=output_style,
                    )
                )
            else:
                # Batched Request Task - format as numbered markdown sections
                changes_md = "\n\n---\n\n".join(
                    f"### Change {i + 1}\n{patch}" for i, patch in enumerate(patches)
                )
                prompt = BATCHED_SUMMARY_USER.format(
                    count=len(patches), changes=changes_md
                )
                tasks.append(
                    SummaryTask(
                        prompt=prompt,
                        is_multiple=True,
                        indices=indices,
                        original_patches=patches,
                        output_style=output_style,
                    )
                )
        return tasks

    def _generate_summaries(
        self,
        annotated_chunk_patches: list[str],
        intent_message: str,
        output_style: Literal["brief", "descriptive"],
    ) -> list[str]:
        """Generate summaries for annotated chunk patches (markdown strings)."""
        from loguru import logger

        if not annotated_chunk_patches:
            return []

        strategy = self.batching_strategy
        if strategy == "auto":
            strategy = "requests" if self.model.is_local() else "prompt"

        # 1. Partition based on strategy and window size
        partitions = self._partition_patches(
            annotated_chunk_patches, strategy, intent_message
        )

        # 2. Create Tasks
        tasks = self._create_summary_tasks(partitions, output_style)

        logger.debug(
            f"Generating summaries for {len(annotated_chunk_patches)} changes (Strategy: {strategy})."
        )

        # 3. Create single callback for progress tracking
        request_count = {"sent": 0, "received": 0}
        pbar = ProgressBarManager.get_pbar()

        def update_callback(status: Literal["sent", "received"]):
            request_count[status] += 1
            if pbar is not None:
                pbar.set_postfix(
                    {
                        "phase": f"summarize chunks {request_count['received']}/{request_count['sent']}"
                    }
                )

        # 4. Invoke Batch
        messages_list = [
            [
                {
                    "role": "system",
                    "content": self._get_summary_system_prompt(
                        t.output_style, t.is_multiple, intent_message
                    ),
                },
                {"role": "user", "content": t.prompt},
            ]
            for t in tasks
        ]
        responses = self.model.invoke_batch(
            messages_list, update_callback=update_callback
        )

        # 5. Process Results
        # We pre-allocate the result list to maintain order
        final_summaries = [""] * len(annotated_chunk_patches)

        for task, response in zip(tasks, responses, strict=True):
            if not task.is_multiple:
                # Single task: simple cleanup + sanitize LLM output
                clean_res = sanitize_llm_text(response.strip('"').strip("'"))
                final_summaries[task.indices[0]] = clean_res
            else:
                batch_summaries = self._parse_markdown_list_response(
                    response, len(task.indices)
                )
                # Distribute results, sanitizing each summary
                for idx, summary in zip(task.indices, batch_summaries, strict=True):
                    final_summaries[idx] = sanitize_llm_text(summary)

        return final_summaries

    def _get_summary_system_prompt(
        self,
        style: Literal["brief", "descriptive"],
        is_multiple: bool,
        intent_message: str,
    ) -> str:
        if style == "brief":
            if is_multiple:
                return BATCHED_SUMMARY_SYSTEM.format(message=intent_message)
            return INITIAL_SUMMARY_SYSTEM.format(message=intent_message)
        else:
            if is_multiple:
                return BATCHED_DESCRIPTIVE_SUMMARY_SYSTEM.format(message=intent_message)
            return INITIAL_DESCRIPTIVE_SUMMARY_SYSTEM.format(message=intent_message)

    # -------------------------------------------------------------------------
    # Cluster Summarization Methods
    # -------------------------------------------------------------------------

    def summarize_clusters(
        self,
        clusters: dict[int, list[str]],
        user_message: str | None = None,
        source_style: Literal["brief", "descriptive"] = "brief",
    ) -> dict[int, str]:
        """Generate combined commit messages for clusters of related summaries.

        Args:
            clusters: Dict mapping cluster_id to list of summaries in that cluster
            intent_message: Optional user-provided intent message

        Returns:
            Dict mapping cluster_id to combined commit message
        """
        from loguru import logger

        if not clusters:
            return {}

        formatted_intent = self._create_user_guidance_message(user_message)

        strategy = self.batching_strategy
        if strategy == "auto":
            strategy = "requests" if self.model.is_local() else "prompt"

        # Partition clusters
        partitions = self._partition_cluster_summaries(
            clusters, strategy, formatted_intent
        )

        # Create tasks
        cluster_tasks = self._create_cluster_summary_tasks(partitions, source_style)

        logger.debug(
            f"Generating cluster summaries for {len(clusters)} clusters (Strategy: {strategy})."
        )

        # 3. Create single callback for progress tracking
        cluster_progress_count = {"sent": 0, "received": 0}
        pbar = ProgressBarManager.get_pbar()

        def cluster_callback(status: Literal["sent", "received"]):
            cluster_progress_count[status] += 1
            if pbar is not None:
                pbar.set_postfix(
                    {
                        "phase": f"finalize summaries {cluster_progress_count['received']}/{cluster_progress_count['sent']}"
                    }
                )

        # Invoke batch
        messages_list = [
            [
                {
                    "role": "system",
                    "content": self._get_cluster_system_prompt(
                        t.source_style, t.is_multiple, formatted_intent
                    ),
                },
                {"role": "user", "content": t.prompt},
            ]
            for t in cluster_tasks
        ]
        responses = self.model.invoke_batch(
            messages_list, update_callback=cluster_callback
        )

        # Process results
        cluster_messages_map = {}
        for task, response in zip(cluster_tasks, responses, strict=True):
            if not task.is_multiple:
                # Single cluster: sanitize LLM output
                clean_msg = sanitize_llm_text(response.strip('"').strip("'"))
                cluster_messages_map[task.cluster_ids[0]] = clean_msg
            else:
                batch_messages = self._parse_markdown_list_response(
                    response, len(task.cluster_ids)
                )
                # Map results, sanitizing each message
                for cluster_id, message in zip(
                    task.cluster_ids, batch_messages, strict=True
                ):
                    cluster_messages_map[cluster_id] = sanitize_llm_text(message)

        return cluster_messages_map

    def _get_cluster_system_prompt(
        self,
        source_style: Literal["brief", "descriptive"],
        is_multiple: bool,
        intent_message: str,
    ) -> str:
        if source_style == "brief":
            if is_multiple:
                return BATCHED_CLUSTER_SUMMARY_SYSTEM.format(message=intent_message)
            return CLUSTER_SUMMARY_SYSTEM.format(message=intent_message)
        else:
            if is_multiple:
                return BATCHED_CLUSTER_FROM_DESCRIPTIVE_SUMMARY_SYSTEM.format(
                    message=intent_message
                )
            return CLUSTER_FROM_DESCRIPTIVE_SUMMARY_SYSTEM.format(
                message=intent_message
            )

    def _partition_cluster_summaries(
        self, clusters: dict[int, list[str]], strategy: str, intent_message: str
    ) -> list[list[tuple[int, list[str]]]]:
        """Partition cluster summaries into groups for batching."""
        base_prompt_cost = self._estimate_tokens(
            BATCHED_CLUSTER_SUMMARY_SYSTEM.format(message=intent_message)
        ) + self._estimate_tokens(BATCHED_CLUSTER_SUMMARY_USER)

        cluster_items = list(clusters.items())

        def cost_fn(item: tuple[int, list[str]]) -> int:
            _, summaries = item
            summaries_text = "\n".join(f"- {s}" for s in summaries)
            return self._estimate_tokens(summaries_text)

        return self._partition_items(cluster_items, cost_fn, base_prompt_cost, strategy)

    def _create_cluster_summary_tasks(
        self,
        partitions: list[list[tuple[int, list[str]]]],
        source_style: Literal["brief", "descriptive"],
    ) -> list[ClusterSummaryTask]:
        """Convert partitions into cluster summary tasks."""
        tasks = []
        for group in partitions:
            cluster_ids = [item[0] for item in group]
            summaries_groups = [item[1] for item in group]

            if len(group) == 1:
                # Single cluster request
                summaries_text = "\n".join(f"- {s}" for s in summaries_groups[0])
                prompt = CLUSTER_SUMMARY_USER.format(summaries=summaries_text)
                tasks.append(
                    ClusterSummaryTask(
                        prompt=prompt,
                        is_multiple=False,
                        cluster_ids=cluster_ids,
                        summaries_groups=summaries_groups,
                        source_style=source_style,
                    )
                )
            else:
                # Batched cluster request - format as numbered markdown groups
                groups_md = "\n\n".join(
                    f"### Group {i + 1}\n"
                    + "\n".join(f"- {s}" for s in group_summaries)
                    for i, group_summaries in enumerate(summaries_groups)
                )
                if source_style == "descriptive":
                    prompt = BATCHED_CLUSTER_FROM_DESCRIPTIVE_SUMMARY_USER.format(
                        count=len(group), groups=groups_md
                    )
                else:
                    prompt = BATCHED_CLUSTER_SUMMARY_USER.format(
                        count=len(group), groups=groups_md
                    )

                tasks.append(
                    ClusterSummaryTask(
                        prompt=prompt,
                        is_multiple=True,
                        cluster_ids=cluster_ids,
                        summaries_groups=summaries_groups,
                        source_style=source_style,
                    )
                )
        return tasks
