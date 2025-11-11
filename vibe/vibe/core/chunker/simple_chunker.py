from typing import List
from ..data.chunk import Chunk
from ..semantic_grouper.context_manager import ContextManager


class SimpleChunker:
    def chunk(self, diff_chunks: list[Chunk], context_manager : ContextManager) -> list[Chunk]:
        """Just returns as is"""
        return diff_chunks
