# -----------------------------------------------------------------------------
# dslate - Dual Licensed Software
# Copyright (c) 2025 Adem Can
#
# This file is part of DSLATE.
#
# DSLATE is available under a dual-license:
#   1. AGPLv3 (Affero General Public License v3)
#      - See LICENSE.txt and LICENSE-AGPL.txt
#      - Online: https://www.gnu.org/licenses/agpl-3.0.html
#
#   2. Commercial License
#      - For proprietary or revenue-generating use,
#        including SaaS, embedding in closed-source software,
#        or avoiding AGPL obligations.
#      - See LICENSE.txt and COMMERCIAL-LICENSE.txt
#      - Contact: ademfcan@gmail.com
#
# By using this file, you agree to the terms of one of the two licenses above.
# -----------------------------------------------------------------------------


import time

from dslate.core.grouper.interface import LogicalGrouper

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
