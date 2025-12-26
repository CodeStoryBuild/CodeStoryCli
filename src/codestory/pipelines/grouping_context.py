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
from typing import Literal

from loguru import logger

from codestory.core.data.chunk import Chunk
from codestory.core.data.commit_group import CommitGroup
from codestory.core.data.immutable_chunk import ImmutableChunk
from codestory.core.embeddings.embedder import Embedder
from codestory.core.grouper.embedding_grouper import EmbeddingGrouper
from codestory.core.grouper.interface import LogicalGrouper
from codestory.core.grouper.single_grouper import SingleGrouper
from codestory.core.llm.codestory_adapter import CodeStoryAdapter
from codestory.core.logging.utils import describe_chunk, time_block
from codestory.core.relevance_filter.relevance_filter import (
    RelevanceFilter,
    RelevanceFilterConfig,
)
from codestory.core.secret_scanner.secret_scanner import ScannerConfig, filter_hunks
from codestory.core.semantic_grouper.context_manager import ContextManager
from codestory.core.semantic_grouper.semantic_grouper import SemanticGrouper
from codestory.pipelines.diff_context import DiffContext


@dataclass(frozen=True)
class GroupingConfig:
    """Configuration for the grouping pipeline."""

    fallback_grouping_strategy: Literal[
        "all_together",
        "by_file_path",
        "by_file_name",
        "by_file_extension",
        "all_alone",
    ]
    relevance_filter_level: Literal["safe", "standard", "strict", "none"]
    secret_scanner_aggression: Literal["safe", "standard", "strict", "none"]

    batching_strategy: Literal["auto", "requests", "prompt"] = "auto"
    cluster_strictness: float = 0.5

    relevance_intent: str | None = None
    guidance_message: str | None = None
    model: CodeStoryAdapter | None = None
    embedder: Embedder | None = None

    def should_filter_relevance(self) -> bool:
        return self.relevance_filter_level != "none" and self.model is not None

    def should_filter_secrets(self) -> bool:
        return self.secret_scanner_aggression != "none"

    def can_use_embedding_grouper(self) -> bool:
        return self.model is not None and self.embedder is not None


class GroupingContext:
    """
    Handles the grouping pipeline: semantic grouping, filtering, and logical grouping.

    This class takes raw diff chunks and produces final logical commit groups by:
    1. Running semantic grouping to organize by code structure
    2. Optionally filtering secrets
    3. Optionally filtering by relevance
    4. Running logical grouping (embedding or single)
    """

    def __init__(
        self,
        diff_context: DiffContext,
        grouping_config: GroupingConfig,
    ):
        regular_chunks = diff_context.get_regular_chunks()
        immutable_chunks = diff_context.get_immutable_chunks()
        context_manager = diff_context.get_context_manager()

        # Run semantic grouping on regular chunks
        if diff_context.has_regular_chunks():
            with time_block("semantic grouping"):
                semantic_grouper = SemanticGrouper(
                    grouping_config.fallback_grouping_strategy
                )
                semantic_chunks = semantic_grouper.group_chunks(
                    regular_chunks, context_manager
                )
        else:
            semantic_chunks = []

        # Filter secrets if configured
        if grouping_config.should_filter_secrets():
            semantic_chunks, immutable_chunks = self._filter_secrets(
                semantic_chunks,
                immutable_chunks,
                grouping_config.secret_scanner_aggression,
            )

        # Filter by relevance if configured
        if grouping_config.should_filter_relevance():
            semantic_chunks, immutable_chunks = self._filter_relevance(
                semantic_chunks,
                immutable_chunks,
                grouping_config.relevance_filter_level,
                grouping_config.relevance_intent,
                grouping_config.model,
                context_manager,
            )

        # Log warning if relevance filter configured but can't be used
        if (
            grouping_config.relevance_filter_level != "none"
            and grouping_config.model is None
        ):
            logger.warning(
                "Relevance filter level is set to '{level}' but no model is configured",
                level=grouping_config.relevance_filter_level,
            )

        # Take semantically valid, filtered chunks, and group them into logical commits
        with time_block("logical_grouping"):
            if grouping_config.can_use_embedding_grouper():
                grouper: LogicalGrouper = EmbeddingGrouper(
                    grouping_config.model,
                    grouping_config.embedder,
                    grouping_config.batching_strategy,
                    grouping_config.cluster_strictness,
                )
            else:
                grouper = SingleGrouper()

            logical_groups: list[CommitGroup] = grouper.group_chunks(
                semantic_chunks,
                immutable_chunks,
                context_manager,
                grouping_config.guidance_message,
            )

        self.final_semantic_chunks = semantic_chunks
        self.final_immutable_chunks = immutable_chunks
        self.final_logical_groups = logical_groups

    def _filter_secrets(
        self,
        semantic_chunks: list[Chunk],
        immutable_chunks: list[ImmutableChunk],
        secret_scanner_aggression: str,
    ) -> tuple[list[Chunk], list[ImmutableChunk]]:
        """Filter out chunks containing potential secrets."""
        scanner_config = ScannerConfig(aggression=secret_scanner_aggression)

        with time_block("secret_scanning"):
            (
                semantic_chunks,
                immutable_chunks,
                rejected_chunks,
            ) = filter_hunks(
                semantic_chunks,
                immutable_chunks,
                config=scanner_config,
            )

            if rejected_chunks:
                logger.info(
                    f"Rejected {len(rejected_chunks)} chunks due to potential hardcoded secrets"
                )
                logger.info("---------- affected chunks ----------")
                for chunk in rejected_chunks:
                    logger.info(describe_chunk(chunk))
                logger.info("These groups will stay as uncommitted changes\n")

            return semantic_chunks, immutable_chunks

    def _filter_relevance(
        self,
        semantic_chunks: list[Chunk],
        immutable_chunks: list[ImmutableChunk],
        relevance_filter_level: str,
        relevance_intent: str | None,
        model: CodeStoryAdapter,
        context_manager: ContextManager,
    ) -> tuple[list[Chunk], list[ImmutableChunk]]:
        """Filter out chunks not relevant to the commit intent."""
        with time_block("relevance_filtering"):
            relevance_filter = RelevanceFilter(
                model,
                RelevanceFilterConfig(level=relevance_filter_level),
            )

            (
                semantic_chunks,
                immutable_chunks,
                rejected_relevance,
            ) = relevance_filter.filter(
                semantic_chunks,
                immutable_chunks,
                intent=relevance_intent,
                context_manager=context_manager,
            )

        if rejected_relevance:
            logger.info(
                f"Rejected {len(rejected_relevance)} chunks due to not being relevant for the commit"
            )
            logger.info("---------- affected chunks ----------")
            for chunk in rejected_relevance:
                logger.info(describe_chunk(chunk))
            logger.info("These chunks will simply stay as uncommitted changes\n")

        return semantic_chunks, immutable_chunks
