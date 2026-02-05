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

from codestory.core.diff.data.line_changes import Addition, Removal
from codestory.core.diff.data.standard_diff_chunk import StandardDiffChunk
from codestory.core.diff.utils.chunk_merger import merge_diff_chunks_by_file


def _chunk(parsed_content, old_start=1):
    return StandardDiffChunk(
        base_hash="base",
        new_hash="head",
        old_file_path=b"file.txt",
        new_file_path=b"file.txt",
        parsed_content=parsed_content,
        old_start=old_start,
    )


def test_merge_preserves_parsed_content_order():
    # Overlapping ranges force a merge. We want the merged chunk to preserve
    # the original ordering of parsed_content across chunks.
    chunk_a = _chunk(
        [
            Removal(1, 1, b"old_a"),
            Removal(2, 2, b"old_b"),
            Addition(2, 2, b"new_b"),
        ],
        old_start=1,
    )
    chunk_b = _chunk(
        [
            Removal(2, 2, b"old_b2"),
            Addition(2, 2, b"new_b2"),
        ],
        old_start=2,
    )

    merged = merge_diff_chunks_by_file([chunk_a, chunk_b])
    assert len(merged) == 1

    merged_items = merged[0].parsed_content
    assert merged_items == chunk_a.parsed_content + chunk_b.parsed_content
