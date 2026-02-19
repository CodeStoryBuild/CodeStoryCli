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

from dataclasses import dataclass
from typing import cast

from codestory.core.diff.data.atomic_container import AtomicContainer
from codestory.core.diff.data.commit_group import CommitGroup
from codestory.core.diff.data.composite_container import CompositeContainer
from codestory.core.diff.data.standard_diff_chunk import StandardDiffChunk
from codestory.core.diff.pipeline.grouper import Grouper


@dataclass(frozen=True)
class _SizedGroup:
    group: CommitGroup
    size: int


class MinCommitSizeGrouper(Grouper):
    """Ensures generated commit groups respect a minimum line-change size."""

    def __init__(self, base_grouper: Grouper, min_size: int | None):
        self.base_grouper = base_grouper
        self.min_size = min_size

    def group(self, containers: list[AtomicContainer]) -> list[CommitGroup]:
        groups = cast(list[CommitGroup], self.base_grouper.group(containers))

        if not groups or self.min_size is None or len(groups) <= 1:
            return groups

        sized_groups = [
            _SizedGroup(group=group, size=self._calculate_group_size(group))
            for group in groups
        ]

        while len(sized_groups) > 1:
            undersized = [
                idx
                for idx, sized_group in enumerate(sized_groups)
                if sized_group.size < self.min_size
            ]
            if not undersized:
                break

            smallest_idx = min(
                undersized, key=lambda idx: (sized_groups[idx].size, idx)
            )
            partner_idx = min(
                (idx for idx in range(len(sized_groups)) if idx != smallest_idx),
                key=lambda idx: (sized_groups[idx].size, idx),
            )

            left_idx, right_idx = sorted((smallest_idx, partner_idx))
            merged_group = self._merge_commit_groups(
                [sized_groups[left_idx].group, sized_groups[right_idx].group]
            )

            sized_groups[left_idx] = _SizedGroup(
                group=merged_group, size=self._calculate_group_size(merged_group)
            )
            sized_groups.pop(right_idx)

        return [sized_group.group for sized_group in sized_groups]

    def _calculate_group_size(self, group: CommitGroup) -> int:
        size = 0
        for chunk in group.get_atomic_chunks():
            if isinstance(chunk, StandardDiffChunk):
                # Count content edits by total removed + added lines.
                line_changes = chunk.old_len() + chunk.new_len()
                size += line_changes if line_changes > 0 else 1
            else:
                size += 1
        return size

    def _merge_commit_groups(self, groups: list[CommitGroup]) -> CommitGroup:
        merged_containers: list[AtomicContainer] = []
        for group in groups:
            if isinstance(group.container, CompositeContainer):
                merged_containers.extend(group.container.containers)
            else:
                merged_containers.append(group.container)

        merged_container = (
            merged_containers[0]
            if len(merged_containers) == 1
            else CompositeContainer(merged_containers)
        )

        commit_messages = [
            group.commit_message.strip()
            for group in groups
            if group.commit_message and group.commit_message.strip()
        ]
        if not commit_messages:
            combined_message = "Combined related changes"
        elif len(commit_messages) == 1:
            combined_message = commit_messages[0]
        else:
            combined_message = " + ".join(commit_messages)

        return CommitGroup(
            container=merged_container,
            commit_message=combined_message,
        )
