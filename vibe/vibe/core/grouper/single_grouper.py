import time
from typing import List

from vibe.core.grouper.interface import LogicalGrouper
from ..data.models import CommitGroup
from .interface import Groupable


class SingleGrouper(LogicalGrouper):
    def group_chunks(
        self, chunks: List[Groupable], message: str, on_progress=None
    ) -> List[CommitGroup]:
        """Return a list of ChunkGroup"""
        groups: List[CommitGroup] = []
        id = 0
        g_time = time.time()
        for chunk in chunks:
            group = CommitGroup(
                [chunk],
                str(id),
                f"AUTOGEN{int(g_time)}-Group-{id}",
                "Auto gen commit message",
            )
            groups.append(group)
            id += 1

        return groups
