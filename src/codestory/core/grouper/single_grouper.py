# -----------------------------------------------------------------------------
# /*
#  * Copyright (C) 2025 CodeStory
#  *
#  * This program is free software; you can redistribute it and/or modify
#  * it under the terms of the GNU General Public License as published by
#  * the Free Software Foundation; Version 2.
#  *
#  * This program is distributed in the hope that it will be useful,
#  * but WITHOUT ANY WARRANTY; without even the implied warranty of
#  * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  * GNU General Public License for more details.
#  *
#  * You should have received a copy of the GNU General Public License
#  * along with this program; if not, you can contact us at support@codestory.build
#  */
# -----------------------------------------------------------------------------

import time

from codestory.core.data.chunk import Chunk
from codestory.core.data.commit_group import CommitGroup
from codestory.core.data.immutable_chunk import ImmutableChunk
from codestory.core.grouper.interface import LogicalGrouper


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
