import time

from vibe.core.grouper.interface import LogicalGrouper

from ..data.chunk import Chunk
from ..data.immutable_chunk import ImmutableChunk
from ..data.commit_group import CommitGroup


class SingleGrouper(LogicalGrouper):
    def group_chunks(
        self,
        chunks: list[Chunk],
        immut_chunks: list[ImmutableChunk],
        message: str,
        on_progress=None,
    ) -> list[CommitGroup]:
        """Return a list of ChunkGroup"""
        groups: list[CommitGroup] = []
        id_ = 0
        g_time = time.time()
        for chunk in chunks:
            group = CommitGroup(
                [chunk],
                str(id_),
                f"AUTOGEN{int(g_time)}-Group-{id_}",
                "Auto gen commit message",
            )
            groups.append(group)
            id_ += 1

        for chunk in immut_chunks:
            group = CommitGroup(
                [chunk],
                str(id_),
                f"AUTOGEN{int(g_time)}-Group-{id_}",
                "Auto gen commit message",
            )
            groups.append(group)
            id_ += 1

        return groups
