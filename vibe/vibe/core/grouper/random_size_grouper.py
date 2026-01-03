import random
from typing import List, Optional
from ..data.models import CommitGroup, ProgressCallback
from .interface import AIGrouper
from .interface import Groupable


class RandomSizeGrouper(AIGrouper):
    def __init__(self, size: int):
        self.size = size

    def group_chunks(
        self,
        chunks: List[Groupable],
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
                commit_message=f"random group #{ct}",
            )
            groups.append(group)
            if on_progress:
                on_progress(
                    len(groups) / ((len(shuffled) + self.size - 1) // self.size)
                )

            ct += 1
        return groups
