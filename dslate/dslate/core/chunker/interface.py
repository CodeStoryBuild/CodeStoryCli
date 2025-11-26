# -----------------------------------------------------------------------------
# dslate - Dual Licensed Software
# Copyright (c) 2025 Adem Can
#
# This file is part of DSLATE.
#
# DSLATE is available under a dual-license:
#   1. AGPLv3 (Affero General Public License v3)
#      - See LICENSE.txt and LICENSE-AGPL.txt
#      - Online: https://www.gnu.org/licenses/agpl-3.0.html
#
#   2. Commercial License
#      - For proprietary or revenue-generating use,
#        including SaaS, embedding in closed-source software,
#        or avoiding AGPL obligations.
#      - See LICENSE.txt and COMMERCIAL-LICENSE.txt
#      - Contact: ademfcan@gmail.com
#
# By using this file, you agree to the terms of one of the two licenses above.
# -----------------------------------------------------------------------------


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
