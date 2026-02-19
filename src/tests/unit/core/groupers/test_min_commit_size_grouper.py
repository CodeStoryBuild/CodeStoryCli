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

from typing import cast

from codestory.core.diff.data.atomic_container import AtomicContainer
from codestory.core.diff.data.commit_group import CommitGroup
from codestory.core.diff.data.line_changes import Addition
from codestory.core.diff.data.standard_diff_chunk import StandardDiffChunk
from codestory.core.diff.pipeline.grouper import Grouper
from codestory.core.groupers.min_commit_size_grouper import MinCommitSizeGrouper


class StaticGrouper(Grouper):
    def __init__(self, groups: list[CommitGroup]):
        self.groups = groups

    def group(self, containers: list[AtomicContainer]) -> list[AtomicContainer]:
        return cast(list[AtomicContainer], self.groups)


def _make_group(message: str, size: int, path: bytes) -> CommitGroup:
    parsed_content = [
        Addition(old_line=1, abs_new_line=i + 1, content=b"line\n") for i in range(size)
    ]
    chunk = StandardDiffChunk(
        base_hash="base",
        new_hash="new",
        old_file_path=path,
        new_file_path=path,
        parsed_content=parsed_content,
        old_start=1,
    )
    return CommitGroup(container=chunk, commit_message=message)


def test_passthrough_when_min_size_disabled():
    groups = [_make_group("a", 1, b"a.py"), _make_group("b", 1, b"b.py")]
    grouper = MinCommitSizeGrouper(StaticGrouper(groups), min_size=None)

    result = grouper.group([])

    assert result == groups


def test_merges_smallest_groups_first():
    groups = [
        _make_group("smallest", 1, b"a.py"),
        _make_group("largest", 4, b"b.py"),
        _make_group("next-smallest", 2, b"c.py"),
    ]
    grouper = MinCommitSizeGrouper(StaticGrouper(groups), min_size=3)

    result = grouper.group([])

    assert len(result) == 2
    assert result[0].commit_message == "smallest + next-smallest"
    assert len(result[0].get_atomic_chunks()) == 2
    assert result[1].commit_message == "largest"


def test_keeps_merging_until_threshold_or_one_group_left():
    groups = [
        _make_group("one", 1, b"a.py"),
        _make_group("two", 1, b"b.py"),
        _make_group("three", 5, b"c.py"),
    ]
    grouper = MinCommitSizeGrouper(StaticGrouper(groups), min_size=3)

    result = grouper.group([])

    assert len(result) == 1
    assert len(result[0].get_atomic_chunks()) == 3
    assert result[0].commit_message == "one + two + three"


def test_does_not_merge_when_all_groups_meet_threshold():
    groups = [_make_group("first", 3, b"a.py"), _make_group("second", 5, b"b.py")]
    grouper = MinCommitSizeGrouper(StaticGrouper(groups), min_size=2)

    result = grouper.group([])

    assert result == groups
