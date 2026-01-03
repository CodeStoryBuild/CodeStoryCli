import random
from typing import List, Optional
from ..data.models import CommitGroup, ProgressCallback
from ..data.diff_chunk import DiffChunk
from .interface import GrouperInterface


class RandomSizeGrouper(GrouperInterface):
    def __init__(self, size: int):
        self.size = size

    def group_chunks(
        self,
        chunks: List[DiffChunk],
        message: str,
        on_progress: Optional[ProgressCallback] = None,
    ) -> List[CommitGroup]:
        shuffled = chunks[:]
        random.shuffle(shuffled)
        groups = []
        ct = 0
        for i in range(0, len(shuffled), self.size):
            group_chunks = shuffled[i : i + self.size]
            group = CommitGroup(
                chunks=group_chunks,
                group_id=f"g{ct}",
                commmit_message=f"random group #{ct}",
            )
            groups.append(group)
            if on_progress:
                on_progress(
                    len(groups) / ((len(shuffled) + self.size - 1) // self.size)
                )

            ct += 1
        return groups
