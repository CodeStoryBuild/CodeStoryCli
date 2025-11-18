import time

from vibe.core.grouper.interface import LogicalGrouper

from ..data.chunk import Chunk
from ..data.models import CommitGroup


class SingleGrouper(LogicalGrouper):
    def group_chunks(
        self, chunks: list[Chunk], message: str, on_progress=None
    ) -> list[CommitGroup]:
        """Return a list of ChunkGroup"""
        groups: list[CommitGroup] = []
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
