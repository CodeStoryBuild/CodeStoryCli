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

from typing import Literal

from colorama import Fore, Style

from codestory.context import GlobalContext
from codestory.core.diff.creation.atomic_chunker import AtomicChunker
from codestory.core.diff.creation.diff_creator import DiffCreator
from codestory.core.diff.patch.semantic_patch_generator import SemanticPatchGenerator
from codestory.core.embeddings.clusterer import Clusterer
from codestory.core.filters.cmd_user_filter import CMDUserFilter
from codestory.core.filters.relevance_filter import RelevanceFilter
from codestory.core.filters.secret_filter import ScannerConfig, SecretsFilter
from codestory.core.filters.utils import describe_rejected_changes
from codestory.core.git.git_synthesizer import GitSynthesizer
from codestory.core.groupers.embedding_grouper import EmbeddingGrouper
from codestory.core.groupers.single_grouper import SingleGrouper
from codestory.core.semantic_analysis.annotation.context_manager import (
    ContextManagerBuilder,
)
from codestory.core.semantic_analysis.annotation.file_manager import FileManager
from codestory.core.semantic_analysis.grouping.semantic_grouper import SemanticGrouper
from codestory.core.semantic_analysis.summarization.chunk_summarizer import (
    ContainerSummarizer,
)


class StandardCLIPipeline:
    """Perform Diff -> Atomic Chunking -> Semantic Grouping -> Filters -> Logical Groups
    -> More Filters -> Create Final Commit."""

    def __init__(
        self,
        context: GlobalContext,
        allow_filtering: bool,
        source: Literal["commit", "fix", "clean"],
        fail_on_syntax_errors: bool = False,
    ):
        self.context = context
        self.diff_creator = DiffCreator(self.context.git_interface)
        self.allow_filtering = allow_filtering
        self.source = source
        self.fail_on_syntax_errors = fail_on_syntax_errors

    def run(
        self,
        base_hash: str,
        new_hash: str,
        target: str | list[str] | None = None,
        user_message: str | None = None,
        user_intent: str | None = None,
    ) -> str | None:
        from loguru import logger

        # base diff
        base_chunks = self.diff_creator.get_processed_working_diff(
            base_hash, new_hash, target
        )

        if not base_chunks:
            logger.warning(f"{Fore.YELLOW} No changes to process {Style.RESET_ALL}")
            if self.source == "fix" or self.source == "clean":
                logger.info(f"{Fore.YELLOW}Is this an empty commit?{Style.RESET_ALL}")
            if self.source == "commit":
                logger.info(
                    f"{Fore.YELLOW}If you meant to modify existing git history, please use codestory fix or codestory clean commands{Style.RESET_ALL}"
                )
            return None

        # Create FileManager for centralized file content caching
        file_manager = FileManager(base_chunks, self.context.git_commands)

        # create all contexts
        context_manager = ContextManagerBuilder(
            base_chunks, file_manager, self.fail_on_syntax_errors, old_hash=base_hash
        ).build()

        # split into our atomic chunks
        atomic_chunks = AtomicChunker(
            context_manager, self.context.config.chunking_level
        ).chunk(base_chunks)

        # create semantic groups
        semantic_groups = SemanticGrouper(
            context_manager, self.context.config.fallback_grouping_strategy
        ).group(atomic_chunks)

        # we apply security filter before relevance, so no secrets can be sent to a cloud llm provider
        if self.allow_filtering and self.context.filter_secrets():
            # TODO, plumb in other scanner options
            semantic_groups, rej = SecretsFilter(
                ScannerConfig(aggression=self.context.config.secret_scanner_aggression),
                file_manager,
            ).filter(semantic_groups)
            if rej:
                describe_rejected_changes(
                    rej, "rejected due to detected exposed secrets"
                )

            if not semantic_groups:
                return None

        if self.context.model_enabled():
            semantic_patch_generator = SemanticPatchGenerator(
                semantic_groups,
                file_manager,
                context_lines=2,
                skip_whitespace=True,
            )
            container_summarizer = ContainerSummarizer(
                self.context.get_model(),
                context_manager,
                semantic_patch_generator,
                self.context.config.batching_strategy,
                self.context.config.max_tokens,
            )
            embedder = self.context.get_embedder()

            if self.allow_filtering and self.context.filter_relevance():
                semantic_groups, rej = RelevanceFilter(
                    container_summarizer,
                    embedder,
                    user_intent,
                    self.context.config.relevance_filter_similarity_threshold,
                ).filter(semantic_groups)
                if rej:
                    describe_rejected_changes(
                        rej, "rejected due to not matching user intent"
                    )

                if not semantic_groups:
                    return None

            clusterer = Clusterer(self.context.config.cluster_strictness)
            logical_groups = EmbeddingGrouper(
                container_summarizer,
                self.context.get_embedder(),
                clusterer,
                user_message,
            ).group(semantic_groups)
        else:
            logical_groups = SingleGrouper().group(semantic_groups)

            if self.allow_filtering and self.context.filter_relevance():
                logger.warning(
                    f"{Fore.YELLOW}Relevance Filtering Enabled, But no model provided. Relevance Filtering will be skipped.{Style.RESET_ALL}"
                )

        accepted_groups, rej = CMDUserFilter(
            self.context.config.auto_accept,
            self.context.config.ask_for_commit_message,
            self.allow_filtering,
            file_manager,
            self.context.config.display_diff_type == "semantic",
            self.context.config.silent,
        ).filter(logical_groups)

        if not accepted_groups:
            logger.info("User accepted no groups")
            return None

        synthesizer = GitSynthesizer(self.context.git_commands, file_manager)

        new_commit_hash = synthesizer.execute_plan(
            # atomic chunks are our reference for total changes in a file
            atomic_chunks,
            accepted_groups,
            base_hash,
        )

        return new_commit_hash
