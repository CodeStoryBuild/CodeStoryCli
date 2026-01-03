from typing import List
from ..data.chunk import Chunk


class SimpleChunker:
    def chunk(self, diff_chunks: List[Chunk]) -> List[Chunk]:
        """Just returns as is"""
        return diff_chunks
