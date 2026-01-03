import random

from ..data.chunk import Chunk
from ..data.models import CommitGroup, ProgressCallback
from .interface import LogicalGrouper


class RandomSizeGrouper(LogicalGrouper):
    def __init__(self, size: int):
        self.size = size

    def group_chunks(
        self,
        chunks: list[Chunk],
        message: str,
        on_progress: ProgressCallback | None = None,
    ) -> list[CommitGroup]:
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
