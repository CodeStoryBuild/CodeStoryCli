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

from codestory.core.chunker.atomic_chunker import AtomicChunker
from codestory.core.data.diff_chunk import DiffChunk
from codestory.core.data.immutable_chunk import ImmutableChunk
from codestory.core.file_reader.git_file_reader import GitFileReader
from codestory.core.git_commands.git_commands import GitCommands
from codestory.core.logging.utils import log_chunks, time_block
from codestory.core.semantic_grouper.context_manager import ContextManager


class DiffContext:
    """
    Encapsulates the diff generation and context analysis for a commit range.

    This class handles:
    1. Getting the processed diff between two commits
    2. Initializing the context manager for semantic analysis
    3. Running atomic chunking to create the smallest valid change units
    """

    def __init__(
        self,
        git_commands: GitCommands,
        base_commit_hash: str,
        new_commit_hash: str,
        target: list[str] | None = None,
        chunking_level: Literal["none", "full_files", "all_files"] = "all_files",
        fail_on_syntax_errors: bool = False,
    ):
        # Get the diff between base and new commit
        with time_block("raw_diff_generation_ms"):
            raw_chunks, immutable_chunks = git_commands.get_processed_working_diff(
                base_commit_hash,
                new_commit_hash,
                target,
            )

        log_chunks(
            "raw_diff_generation_ms (with immutable groups)",
            raw_chunks,
            immutable_chunks,
        )

        # Initialize context_manager for semantic analysis
        with time_block("context manager init"):
            file_reader = GitFileReader(git_commands)
            context_manager = ContextManager(
                raw_chunks,
                file_reader,
                base_commit_hash,
                new_commit_hash,
                fail_on_syntax_errors,
            )

        # Run atomic chunker to create smallest valid change units
        chunker = AtomicChunker(chunking_level)
        if raw_chunks:
            with time_block("atomic chunking"):
                raw_chunks: list[DiffChunk] = chunker.chunk(raw_chunks, context_manager)

            log_chunks("atomic chunking", raw_chunks, immutable_chunks)

        self.raw_chunks = raw_chunks
        self.immutable_chunks = immutable_chunks
        self.context_manager = context_manager

    def has_regular_chunks(self) -> bool:
        return bool(self.raw_chunks)

    def has_immutable_chunks(self) -> bool:
        return bool(self.immutable_chunks)

    def has_changes(self) -> bool:
        return self.has_immutable_chunks() or self.has_regular_chunks()

    def get_regular_chunks(self) -> list[DiffChunk]:
        return self.raw_chunks

    def get_immutable_chunks(self) -> list[ImmutableChunk]:
        return self.immutable_chunks

    def get_context_manager(self) -> ContextManager:
        return self.context_manager
