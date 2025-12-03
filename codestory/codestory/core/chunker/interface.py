"""
-----------------------------------------------------------------------------
/*
 * Copyright (C) 2025 CodeStory
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; Version 2.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, you can contact us at support@codestory.build.
 */
-----------------------------------------------------------------------------
"""

"""
ChunkerInterface

This interface is responsible for subdividing raw diff hunks into smaller, atomic chunks.

Responsibilities:
- Split hunks into sub-hunks, functions, logical blocks, or line-level chunks
- Provide input suitable for semantic grouping
- Optional: syntax-aware or AI-driven splitting

Possible Implementations:
- HunkChunker: returns hunks unchanged
- SubHunkChunker: splits hunks based on syntax, blank lines, or functions
- AIChunker: uses an AI model to propose atomic chunks semantically
- CustomChunker: user-defined rules for splitting

Notes:
- Must propagate old/new line numbers and file paths so chunks can be committed individually
- Sub-hunk splitting is an optional but powerful enhancement
- Should preserve metadata like file_path and line numbers
- Enables fine-grained commits later in the pipeline
"""

from abc import ABC, abstractmethod

from ..data.chunk import Chunk
from ..semantic_grouper.context_manager import ContextManager


class MechanicalChunker(ABC):
    @abstractmethod
    def chunk(
        self, diff_chunks: list[Chunk], context_manager: ContextManager
    ) -> list[Chunk]:
        """Split hunks into smaller chunks or sub-hunks"""
