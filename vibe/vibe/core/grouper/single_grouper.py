import time
from typing import List, Dict

from vibe.core.grouper.interface import GrouperInterface
from ..data.models import CommitGroup
from ..data.diff_chunk import DiffChunk

class SingleGrouper(GrouperInterface):
    def group_chunks(self, chunks: List[DiffChunk]) -> List[CommitGroup]:
        """Return a list of ChunkGroup"""
        groups : List[CommitGroup] = []
        id = 0
        g_time = time.time()
        for chunk in chunks:
            group = CommitGroup([chunk], str(id), f"AUTOGEN{int(g_time)}-Group-{id}", "Auto gen commit message")
            groups.append(group)
            id+=1

        return groups