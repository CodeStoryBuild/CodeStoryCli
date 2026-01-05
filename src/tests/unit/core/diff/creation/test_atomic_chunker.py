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

from unittest.mock import Mock

import pytest

from codestory.core.diff.creation.atomic_chunker import AtomicChunker
from codestory.core.diff.data.composite_container import CompositeContainer
from codestory.core.diff.data.line_changes import Addition, Removal
from codestory.core.diff.data.standard_diff_chunk import StandardDiffChunk

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def create_chunk(
    content_lines, old_path=b"file.txt", new_path=b"file.txt", start_line=1
):
    """Helper to create a StandardDiffChunk with specific content."""
    parsed_content = []
    current_old = start_line
    current_new = start_line

    for line in content_lines:
        if line.startswith(b"+"):
            parsed_content.append(Addition(current_old, current_new, line[1:]))
            current_new += 1
        elif line.startswith(b"-"):
            parsed_content.append(Removal(current_old, current_new, line[1:]))
            current_old += 1

    return StandardDiffChunk(
        base_hash="test_base",
        new_hash="test_new",
        old_file_path=old_path,
        new_file_path=new_path,
        parsed_content=parsed_content,
        old_start=start_line,
    )


@pytest.fixture
def context_manager():
    cm = Mock()
    # Default: no context info
    cm.get_context.return_value = None
    return cm


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


def test_split_hunks_true(context_manager):
    """Test that chunks are split when chunking is True."""
    chunker = AtomicChunker(context_manager=context_manager, chunking_level="all_files")

    # Chunk with 2 additions
    chunk = create_chunk([b"+line1", b"+line2"])

    result = chunker.chunk([chunk])

    # Should be split into 2 chunks
    assert len(result) == 2
    assert isinstance(result[0], StandardDiffChunk)
    assert result[0].parsed_content[0].content == b"line1"
    assert result[1].parsed_content[0].content == b"line2"


def test_split_hunks_false(context_manager):
    """Test that chunks are NOT split when chunking is False."""
    chunker = AtomicChunker(context_manager=context_manager, chunking_level="none")

    chunk = create_chunk([b"+line1", b"+line2"])

    result = chunker.chunk([chunk])

    assert len(result) == 1
    assert result[0] is chunk


def test_group_whitespace_context(context_manager):
    """Test grouping of whitespace-only chunks."""
    chunker = AtomicChunker(context_manager=context_manager, chunking_level="all_files")

    # 3 chunks: code, whitespace, code
    create_chunk([b"+code1"])
    create_chunk([b"+   "])  # Whitespace
    create_chunk([b"+code2"])

    # Pass them as a single chunk to be split
    # Note: AtomicChunker splits the input chunk first
    # But here we can pass pre-split chunks if we want to test _group_by_chunk_predicate directly
    # OR we can pass a single chunk and let it split.

    # Let's pass a single chunk that will be split
    big_chunk = create_chunk([b"+code1", b"+   ", b"+code2"])

    result = chunker.chunk([big_chunk])

    # Logic:
    # 1. Split into atomic chunks with context grouping.
    # 2. c2 is context (blank/whitespace).
    # 3. c1 and c3 are not.
    # 4. c2 should be attached to c3 as a single merged StandardDiffChunk.
    # Result: [StandardDiffChunk(code1), StandardDiffChunk(whitespace+code2)]

    assert len(result) == 2
    assert isinstance(result[0], StandardDiffChunk)
    assert result[0].parsed_content[0].content == b"code1"

    # Second chunk should be a merged StandardDiffChunk with whitespace + code2
    assert isinstance(result[1], StandardDiffChunk)
    assert len(result[1].parsed_content) == 2
    assert result[1].parsed_content[0].content == b"   "
    assert result[1].parsed_content[1].content == b"code2"


def test_group_comment_context(context_manager):
    """Test grouping of comment lines via ContextManager."""
    # Setup ContextManager to identify line 2 (index 1) as a comment
    file_ctx = Mock()
    file_ctx.comment_map.pure_comment_lines = {1}  # 0-indexed line 1 (second line)
    context_manager.get_context.return_value = file_ctx

    chunker = AtomicChunker(context_manager=context_manager, chunking_level="all_files")

    # 3 lines: code, comment, code
    # Line indices: 0, 1, 2
    big_chunk = create_chunk([b"+code1", b"+// comment", b"+code2"], start_line=1)
    # Note: start_line=1 means lines are 1, 2, 3.
    # In _line_is_context: line_idx = abs_new_line - 1.
    # Line 1: abs_new_line=1 -> idx=0
    # Line 2: abs_new_line=2 -> idx=1 (Match!)
    # Line 3: abs_new_line=3 -> idx=2

    result = chunker.chunk([big_chunk])

    # Should group comment with next code chunk as a merged StandardDiffChunk
    assert len(result) == 2
    assert isinstance(result[1], StandardDiffChunk)
    assert len(result[1].parsed_content) == 2
    assert result[1].parsed_content[0].content == b"// comment"
    assert result[1].parsed_content[1].content == b"code2"


def test_all_context(context_manager):
    """Test when all chunks are context."""
    chunker = AtomicChunker(context_manager=context_manager, chunking_level="all_files")

    # All whitespace
    big_chunk = create_chunk([b"+ ", b"+  "])

    result = chunker.chunk([big_chunk])

    # Should return a single merged StandardDiffChunk with all context lines
    assert len(result) == 1
    assert isinstance(result[0], StandardDiffChunk)
    assert len(result[0].parsed_content) == 2
    assert result[0].parsed_content[0].content == b" "
    assert result[0].parsed_content[1].content == b"  "


def test_no_context(context_manager):
    """Test when no chunks are context."""
    chunker = AtomicChunker(context_manager=context_manager, chunking_level="all_files")

    big_chunk = create_chunk([b"+code1", b"+code2"])

    result = chunker.chunk([big_chunk])

    # Should remain separate atomic chunks
    assert len(result) == 2
    assert isinstance(result[0], StandardDiffChunk)
    assert isinstance(result[1], StandardDiffChunk)


def test_non_continuous_context_grouping(context_manager):
    """Test grouping of non-continuous chunks (separated by gaps)."""
    chunker = AtomicChunker(context_manager=context_manager, chunking_level="all_files")

    # Chunk 1: context (line 1)
    c1 = create_chunk([b"+ "], start_line=1)
    # Chunk 2: code (line 10)
    c2 = create_chunk([b"+code"], start_line=10)
    # Chunk 3: context (line 20)
    c3 = create_chunk([b"+ "], start_line=20)
    # Chunk 4: context (line 30) (different file)
    c4 = create_chunk(
        [b"+ "], old_path=b"other.txt", new_path=b"other.txt", start_line=30
    )

    result = chunker.chunk([c1, c2, c3, c4])

    # result[0] should be a CompositeContainer for file.txt: [c1, c2, c3]
    # result[1] should be c4 for other.txt
    assert len(result) == 2

    assert isinstance(result[0], CompositeContainer)
    assert len(result[0].containers) == 3
    assert result[0].containers[0] == c1
    # Note: c2 is split by _split_and_group_chunk because level is all_files
    # Wait, c2 has only one line, so it won't be split into multiple.
    assert result[0].containers[1] == c2
    assert result[0].containers[2] == c3

    assert result[1] == c4
