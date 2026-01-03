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

from codestory.core.diff.data.atomic_container import AtomicContainer
from codestory.core.diff.data.commit_group import CommitGroup
from codestory.core.diff.pipeline.grouper import Grouper


class SingleGrouper(Grouper):
    def group(
        self,
        chunks: list[AtomicContainer],
    ) -> list[CommitGroup]:
        groups: list[AtomicContainer] = []
        g_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        for i, container in enumerate(chunks):
            group = CommitGroup(
                container,
                f"Automaticaly Generated Commit #{i + 1} (Time: {g_time})",
            )
            groups.append(group)

        return groups
