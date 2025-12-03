import time

from codestory.core.grouper.interface import LogicalGrouper

from ..data.chunk import Chunk
from ..data.commit_group import CommitGroup
from ..data.immutable_chunk import ImmutableChunk


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
        g_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        for chunk in chunks:
            group = CommitGroup(
                [chunk],
                str(id_),
                f"Automaticaly Generated Commit #{id_} (Time: {g_time})",
                "Auto gen commit message",
            )
            groups.append(group)
            id_ += 1

        for chunk in immut_chunks:
            group = CommitGroup(
                [chunk],
                str(id_),
                f"Automaticaly Generated Commit #{id_} (Time: {g_time}) ",
                "Auto gen commit message",
            )
            groups.append(group)
            id_ += 1

        return groups
