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

from codestory.core.chunker.atomic_chunker import AtomicChunker
from codestory.core.data.composite_diff_chunk import CompositeDiffChunk
from codestory.core.data.diff_chunk import DiffChunk
from codestory.core.data.line_changes import Addition, Removal

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def create_chunk(
    content_lines, old_path=b"file.txt", new_path=b"file.txt", start_line=1
):
    """Helper to create a DiffChunk with specific content."""
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

    return DiffChunk(
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
    """Test that chunks are split when split_hunks is True."""
    chunker = AtomicChunker(split_hunks=True)

    # Chunk with 2 additions
    chunk = create_chunk([b"+line1", b"+line2"])

    result = chunker.chunk([chunk], context_manager)

    # Should be split into 2 chunks
    assert len(result) == 2
    assert isinstance(result[0], DiffChunk)
    assert result[0].parsed_content[0].content == b"line1"
    assert result[1].parsed_content[0].content == b"line2"


def test_split_hunks_false(context_manager):
    """Test that chunks are NOT split when split_hunks is False."""
    chunker = AtomicChunker(split_hunks=False)

    chunk = create_chunk([b"+line1", b"+line2"])

    result = chunker.chunk([chunk], context_manager)

    assert len(result) == 1
    assert result[0] is chunk


def test_group_whitespace_context(context_manager):
    """Test grouping of whitespace-only chunks."""
    chunker = AtomicChunker(split_hunks=True)

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

    result = chunker.chunk([big_chunk], context_manager)

    # Logic:
    # 1. Split into 3 atomic chunks.
    # 2. c2 is context (blank/whitespace).
    # 3. c1 and c3 are not.
    # 4. c2 should be attached to c1 or c3.
    # Implementation preference: next group (c3) if possible, else previous (c1).
    # So c2 attaches to c3.
    # Result: [c1, Composite(c2, c3)]

    assert len(result) == 2
    assert isinstance(result[0], DiffChunk)
    assert result[0].parsed_content[0].content == b"code1"

    assert isinstance(result[1], CompositeDiffChunk)
    assert len(result[1].chunks) == 2
    assert result[1].chunks[0].parsed_content[0].content == b"   "
    assert result[1].chunks[1].parsed_content[0].content == b"code2"


def test_group_comment_context(context_manager):
    """Test grouping of comment lines via ContextManager."""
    chunker = AtomicChunker(split_hunks=True)

    # Setup ContextManager to identify line 2 (index 1) as a comment
    file_ctx = Mock()
    file_ctx.comment_map.pure_comment_lines = {1}  # 0-indexed line 1 (second line)
    context_manager.get_context.return_value = file_ctx

    # 3 lines: code, comment, code
    # Line indices: 0, 1, 2
    big_chunk = create_chunk([b"+code1", b"+// comment", b"+code2"], start_line=1)
    # Note: start_line=1 means lines are 1, 2, 3.
    # In _line_is_context: line_idx = abs_new_line - 1.
    # Line 1: abs_new_line=1 -> idx=0
    # Line 2: abs_new_line=2 -> idx=1 (Match!)
    # Line 3: abs_new_line=3 -> idx=2

    result = chunker.chunk([big_chunk], context_manager)

    # Should group comment with next code chunk
    assert len(result) == 2
    assert isinstance(result[1], CompositeDiffChunk)
    assert result[1].chunks[0].parsed_content[0].content == b"// comment"


def test_all_context(context_manager):
    """Test when all chunks are context."""
    chunker = AtomicChunker(split_hunks=True)

    # All whitespace
    big_chunk = create_chunk([b"+ ", b"+  "])

    result = chunker.chunk([big_chunk], context_manager)

    # Should return a single group (Composite or list of chunks depending on implementation)
    # Implementation: returns [CompositeDiffChunk(all)] if > 1
    assert len(result) == 1
    assert isinstance(result[0], CompositeDiffChunk)
    assert len(result[0].chunks) == 2


def test_no_context(context_manager):
    """Test when no chunks are context."""
    chunker = AtomicChunker(split_hunks=True)

    big_chunk = create_chunk([b"+code1", b"+code2"])

    result = chunker.chunk([big_chunk], context_manager)

    # Should remain separate atomic chunks
    assert len(result) == 2
    assert isinstance(result[0], DiffChunk)
    assert isinstance(result[1], DiffChunk)
