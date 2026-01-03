
from typing import List
from ..data.models import DiffChunk

class SimpleChunker:
    def chunk(self, diff_chunks: List[DiffChunk]) -> List[DiffChunk]:
        """Just returns as is"""
        return diff_chunks
