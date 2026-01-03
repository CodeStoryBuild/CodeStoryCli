"""
Comprehensive tests for DiffChunk.split_into_atomic_chunks() method.

These tests ensure that the atomic chunk splitting functionality respects core invariants:
1. Atomic chunks are truly atomic (single addition, removal, or matched pair)
2. Atomic chunks are disjoint
3. Atomic chunks preserve the original input
4. Atomic chunks are valid DiffChunk instances
"""

import pytest

from vibe.core.data.diff_chunk import DiffChunk
from vibe.core.data.line_changes import Addition, Removal
from vibe.core.checks.chunk_checks import chunks_disjoint


# # ============================================================================
# Helper Functions
# ============================================================================


def assert_is_atomic(chunk: DiffChunk):
    """
    Assert that a chunk is atomic (cannot be split further).
    An atomic chunk has one of these patterns:
    - Single addition only
    - Single removal only
    - Single removal + single addition at same relative position (modification)
    """
    removals = [item for item in chunk.parsed_content if isinstance(item, Removal)]
    additions = [item for item in chunk.parsed_content if isinstance(item, Addition)]

    total_items = len(removals) + len(additions)

    if total_items == 1:
        # Pure addition or pure removal - atomic
        return True
    elif total_items == 2:
        # Must be exactly 1 removal and 1 addition at matching relative positions
        assert (
            len(removals) == 1 and len(additions) == 1
        ), f"Atomic chunk with 2 items must have 1 removal and 1 addition, got {len(removals)} removals and {len(additions)} additions"

        # Check that they're at matching relative positions
        removal = removals[0]
        addition = additions[0]
        rel_removal = removal.line_number - chunk.old_start
        rel_addition = addition.line_number - chunk.new_start

        assert (
            rel_removal == rel_addition
        ), f"Modification atomic chunk has mismatched positions: removal at rel {rel_removal}, addition at rel {rel_addition}"
        return True
    else:
        pytest.fail(
            f"Chunk is not atomic! Has {total_items} items: {len(removals)} removals, {len(additions)} additions"
        )


def assert_atomic_chunks_preserve_input(atomic_chunks: list, original: DiffChunk):
    """Assert that atomic chunks contain exactly the same items as original."""
    original_items = set()
    for item in original.parsed_content:
        original_items.add((type(item).__name__, item.line_number, item.content))

    atomic_items = set()
    for chunk in atomic_chunks:
        for item in chunk.parsed_content:
            atomic_items.add((type(item).__name__, item.line_number, item.content))

    assert atomic_items == original_items, (
        f"Atomic chunks do not preserve input.\n"
        f"Original: {sorted(original_items)}\n"
        f"Atomic: {sorted(atomic_items)}"
    )


# ============================================================================
# Test Cases: Basic Scenarios
# ============================================================================


def test_atomic_pure_additions():
    """Test splitting pure additions into atomic chunks."""
    chunk = DiffChunk(
        new_file_path="test.py",
        old_file_path="test.py",
        parsed_content=[
            Addition(content="line1", line_number=1),
            Addition(content="line2", line_number=2),
            Addition(content="line3", line_number=3),
        ],
        old_start=0,
        new_start=1,
    )

    atomic_chunks = chunk.split_into_atomic_chunks()

    # Should produce 3 atomic chunks (one per addition)
    assert len(atomic_chunks) == 3

    # Each chunk should be atomic
    for atomic_chunk in atomic_chunks:
        assert_is_atomic(atomic_chunk)

    # Should preserve input
    assert_atomic_chunks_preserve_input(atomic_chunks, chunk)

    # Should be disjoint
    assert chunks_disjoint(atomic_chunks)


def test_atomic_pure_removals():
    """Test splitting pure removals into atomic chunks."""
    chunk = DiffChunk(
        new_file_path="test.py",
        old_file_path="test.py",
        parsed_content=[
            Removal(content="line1", line_number=10),
            Removal(content="line2", line_number=11),
            Removal(content="line3", line_number=12),
        ],
        old_start=10,
        new_start=0,
    )

    atomic_chunks = chunk.split_into_atomic_chunks()

    # Should produce 3 atomic chunks (one per removal)
    assert len(atomic_chunks) == 3

    # Each chunk should be atomic
    for atomic_chunk in atomic_chunks:
        assert_is_atomic(atomic_chunk)

    # Should preserve input
    assert_atomic_chunks_preserve_input(atomic_chunks, chunk)

    # Should be disjoint
    assert chunks_disjoint(atomic_chunks)


def test_atomic_matched_modifications():
    """Test splitting matched modifications (replacement) into atomic chunks."""
    chunk = DiffChunk(
        new_file_path="test.py",
        old_file_path="test.py",
        parsed_content=[
            Addition(content="new1", line_number=1),
            Removal(content="old1", line_number=1),
            Addition(content="new2", line_number=2),
            Removal(content="old2", line_number=2),
            Addition(content="new3", line_number=3),
            Removal(content="old3", line_number=3),
        ],
        old_start=1,
        new_start=1,
    )

    atomic_chunks = chunk.split_into_atomic_chunks()

    # Should produce 3 atomic chunks (one per matched pair)
    assert len(atomic_chunks) == 3

    # Each chunk should be atomic (1 removal + 1 addition)
    for atomic_chunk in atomic_chunks:
        assert_is_atomic(atomic_chunk)
        assert len(atomic_chunk.parsed_content) == 2

    # Should preserve input
    assert_atomic_chunks_preserve_input(atomic_chunks, chunk)

    # Should be disjoint
    assert chunks_disjoint(atomic_chunks)


def test_atomic_mixed_pattern():
    """Test splitting mixed pattern (modifications + pure additions/removals)."""
    chunk = DiffChunk(
        new_file_path="test.py",
        old_file_path="test.py",
        parsed_content=[
            Addition(content="new1", line_number=1),
            Removal(content="old1", line_number=1),
            Addition(content="new2", line_number=2),
            Addition(content="new3", line_number=3),
            Removal(content="old4", line_number=2),
        ],
        old_start=1,
        new_start=1,
    )

    atomic_chunks = chunk.split_into_atomic_chunks()

    # The algorithm matches by relative position:
    # Relative position 0: old1 (line 1-1=0) matches new1 (line 1-1=0) -> modification
    # Relative position 1: old4 (line 2-1=1) matches new2 (line 2-1=1) -> modification
    # Relative position 2: new3 (line 3-1=2) has no removal -> pure addition
    # So we get 3 atomic chunks: 2 modifications + 1 pure addition
    assert len(atomic_chunks) == 3

    # Each chunk should be atomic
    for atomic_chunk in atomic_chunks:
        assert_is_atomic(atomic_chunk)

    # Verify the structure: 2 modifications + 1 pure addition
    modifications = [c for c in atomic_chunks if len(c.parsed_content) == 2]
    pure_additions = [
        c
        for c in atomic_chunks
        if len(c.parsed_content) == 1 and isinstance(c.parsed_content[0], Addition)
    ]
    assert (
        len(modifications) == 2
    ), f"Expected 2 modifications, got {len(modifications)}"
    assert (
        len(pure_additions) == 1
    ), f"Expected 1 pure addition, got {len(pure_additions)}"

    # Should preserve input
    assert_atomic_chunks_preserve_input(atomic_chunks, chunk)

    # Should be disjoint
    assert chunks_disjoint(atomic_chunks)


def test_atomic_single_addition():
    """Test that a single addition remains unchanged."""
    chunk = DiffChunk(
        new_file_path="test.py",
        old_file_path="test.py",
        parsed_content=[
            Addition(content="single", line_number=5),
        ],
        old_start=0,
        new_start=5,
    )

    atomic_chunks = chunk.split_into_atomic_chunks()

    # Should produce 1 atomic chunk
    assert len(atomic_chunks) == 1
    assert_is_atomic(atomic_chunks[0])

    # Should preserve input
    assert_atomic_chunks_preserve_input(atomic_chunks, chunk)


def test_atomic_single_removal():
    """Test that a single removal remains unchanged."""
    chunk = DiffChunk(
        new_file_path="test.py",
        old_file_path="test.py",
        parsed_content=[
            Removal(content="single", line_number=10),
        ],
        old_start=10,
        new_start=0,
    )

    atomic_chunks = chunk.split_into_atomic_chunks()

    # Should produce 1 atomic chunk
    assert len(atomic_chunks) == 1
    assert_is_atomic(atomic_chunks[0])

    # Should preserve input
    assert_atomic_chunks_preserve_input(atomic_chunks, chunk)


def test_atomic_single_modification():
    """Test that a single modification remains as one atomic chunk."""
    chunk = DiffChunk(
        new_file_path="test.py",
        old_file_path="test.py",
        parsed_content=[
            Addition(content="new", line_number=5),
            Removal(content="old", line_number=5),
        ],
        old_start=5,
        new_start=5,
    )

    atomic_chunks = chunk.split_into_atomic_chunks()

    # Should produce 1 atomic chunk
    assert len(atomic_chunks) == 1
    assert_is_atomic(atomic_chunks[0])
    assert len(atomic_chunks[0].parsed_content) == 2

    # Should preserve input
    assert_atomic_chunks_preserve_input(atomic_chunks, chunk)


# ============================================================================
# Test Cases: Complex Patterns
# ============================================================================


def test_atomic_unbalanced_additions_removals():
    """Test splitting when there are more additions than removals."""
    chunk = DiffChunk(
        new_file_path="test.py",
        old_file_path="test.py",
        parsed_content=[
            Removal(content="old1", line_number=1),
            Removal(content="old2", line_number=2),
            Addition(content="new1", line_number=1),
            Addition(content="new2", line_number=2),
            Addition(content="new3", line_number=3),
            Addition(content="new4", line_number=4),
        ],
        old_start=1,
        new_start=1,
    )

    atomic_chunks = chunk.split_into_atomic_chunks()

    # Should produce 4 atomic chunks:
    # 2 modifications (old1/new1, old2/new2) + 2 pure additions (new3, new4)
    assert len(atomic_chunks) == 4

    # Each chunk should be atomic
    for atomic_chunk in atomic_chunks:
        assert_is_atomic(atomic_chunk)

    # Should preserve input
    assert_atomic_chunks_preserve_input(atomic_chunks, chunk)

    # Should be disjoint
    assert chunks_disjoint(atomic_chunks)


def test_atomic_large_chunk():
    """Test splitting a large chunk into many atomic chunks."""
    parsed_content = []
    content_lines = []

    # Create 50 modifications
    for i in range(50):
        parsed_content.append(Addition(content=f"new_{i}", line_number=i + 1))
        content_lines.append(f"+new_{i}")
        parsed_content.append(Removal(content=f"old_{i}", line_number=i + 1))
        content_lines.append(f"-old_{i}")

    chunk = DiffChunk(
        new_file_path="large.py",
        old_file_path="large.py",
        parsed_content=parsed_content,
        old_start=1,
        new_start=1,
    )

    atomic_chunks = chunk.split_into_atomic_chunks()

    # Should produce 50 atomic chunks (one per modification)
    assert len(atomic_chunks) == 50

    # Each chunk should be atomic
    for atomic_chunk in atomic_chunks:
        assert_is_atomic(atomic_chunk)
        # Each should be a modification (2 items)
        assert len(atomic_chunk.parsed_content) == 2

    # Should preserve input
    assert_atomic_chunks_preserve_input(atomic_chunks, chunk)

    # Should be disjoint
    assert chunks_disjoint(atomic_chunks)


def test_atomic_interleaved_pattern():
    """Test complex interleaved pattern of additions and removals."""
    chunk = DiffChunk(
        new_file_path="test.py",
        old_file_path="test.py",
        parsed_content=[
            Addition(content="a", line_number=1),
            Addition(content="b", line_number=2),
            Removal(content="x", line_number=1),
            Removal(content="y", line_number=2),
            Addition(content="c", line_number=3),
            Removal(content="z", line_number=3),
        ],
        old_start=1,
        new_start=1,
    )

    atomic_chunks = chunk.split_into_atomic_chunks()

    # Should produce atomic chunks based on relative positions
    assert len(atomic_chunks) > 0

    # Each chunk should be atomic
    for atomic_chunk in atomic_chunks:
        assert_is_atomic(atomic_chunk)

    # Should preserve input
    assert_atomic_chunks_preserve_input(atomic_chunks, chunk)

    # Should be disjoint
    assert chunks_disjoint(atomic_chunks)


def test_atomic_non_matching_line_numbers():
    """Test splitting when additions and removals have different starting positions.

    Note: The algorithm matches by RELATIVE position, not absolute line numbers.
    Even though absolute line numbers differ, relative positions are the same.
    """
    chunk = DiffChunk(
        new_file_path="test.py",
        old_file_path="test.py",
        parsed_content=[
            Removal(content="old1", line_number=10),
            Removal(content="old2", line_number=11),
            Removal(content="old3", line_number=12),
            Addition(content="new1", line_number=20),
            Addition(content="new2", line_number=21),
        ],
        old_start=10,
        new_start=20,
    )

    atomic_chunks = chunk.split_into_atomic_chunks()

    # The algorithm uses RELATIVE positions:
    # old1: 10-10=0, new1: 20-20=0 -> matched (modification)
    # old2: 11-10=1, new2: 21-20=1 -> matched (modification)
    # old3: 12-10=2, no addition at relative 2 -> pure removal
    # Result: 2 modifications + 1 removal = 3 atomic chunks
    assert len(atomic_chunks) == 3

    # Each chunk should be atomic
    for atomic_chunk in atomic_chunks:
        assert_is_atomic(atomic_chunk)

    # Verify the structure: 2 modifications + 1 removal
    modifications = [c for c in atomic_chunks if len(c.parsed_content) == 2]
    pure_removals = [
        c
        for c in atomic_chunks
        if len(c.parsed_content) == 1 and isinstance(c.parsed_content[0], Removal)
    ]
    assert (
        len(modifications) == 2
    ), f"Expected 2 modifications, got {len(modifications)}"
    assert len(pure_removals) == 1, f"Expected 1 pure removal, got {len(pure_removals)}"

    # Should preserve input
    assert_atomic_chunks_preserve_input(atomic_chunks, chunk)

    # Should be disjoint
    assert chunks_disjoint(atomic_chunks)


# ============================================================================
# Test Cases: Edge Cases
# ============================================================================


def test_atomic_empty_content_lines():
    """Test splitting chunks with empty content lines."""
    chunk = DiffChunk(
        new_file_path="test.py",
        old_file_path="test.py",
        parsed_content=[
            Addition(content="", line_number=1),
            Addition(content="line2", line_number=2),
            Addition(content="", line_number=3),
        ],
        old_start=0,
        new_start=1,
    )

    atomic_chunks = chunk.split_into_atomic_chunks()

    # Should produce 3 atomic chunks
    assert len(atomic_chunks) == 3

    # Each chunk should be atomic
    for atomic_chunk in atomic_chunks:
        assert_is_atomic(atomic_chunk)

    # Should preserve input
    assert_atomic_chunks_preserve_input(atomic_chunks, chunk)

    # Should be disjoint
    assert chunks_disjoint(atomic_chunks)


def test_atomic_all_at_same_position():
    """Test splitting multiple changes at the same position."""
    chunk = DiffChunk(
        new_file_path="test.py",
        old_file_path="test.py",
        parsed_content=[
            Addition(content="new1", line_number=5),
            Addition(content="new2", line_number=6),
            Addition(content="new3", line_number=7),
            Removal(content="old1", line_number=5),
            Removal(content="old2", line_number=6),
            Removal(content="old3", line_number=7),
        ],
        old_start=5,
        new_start=5,
    )

    atomic_chunks = chunk.split_into_atomic_chunks()

    # Should produce 3 atomic chunks (matched pairs)
    assert len(atomic_chunks) == 3

    # Each chunk should be atomic
    for atomic_chunk in atomic_chunks:
        assert_is_atomic(atomic_chunk)

    # Should preserve input
    assert_atomic_chunks_preserve_input(atomic_chunks, chunk)

    # Should be disjoint
    assert chunks_disjoint(atomic_chunks)


# ============================================================================
# Test Cases: Validation
# ============================================================================


def test_atomic_chunks_have_valid_file_paths():
    """Test that all atomic chunks preserve the file path."""
    chunk = DiffChunk(
        new_file_path="important/file.py",
        old_file_path="important/file.py",
        parsed_content=[
            Addition(content="line1", line_number=1),
            Addition(content="line2", line_number=2),
            Addition(content="line3", line_number=3),
        ],
        old_start=0,
        new_start=1,
    )

    atomic_chunks = chunk.split_into_atomic_chunks()

    # All atomic chunks should have the same file path
    for atomic_chunk in atomic_chunks:
        assert atomic_chunk.old_file_path == "important/file.py"
        assert atomic_chunk.new_file_path == "important/file.py"


def test_atomic_chunks_are_contiguous():
    """Test that all atomic chunks pass contiguity validation."""
    chunk = DiffChunk(
        new_file_path="test.py",
        old_file_path="test.py",
        parsed_content=[
            Addition(content="new1", line_number=1),
            Removal(content="old1", line_number=1),
            Addition(content="new2", line_number=2),
            Removal(content="old2", line_number=2),
        ],
        old_start=1,
        new_start=1,
    )

    atomic_chunks = chunk.split_into_atomic_chunks()

    # All atomic chunks should be valid (contiguity checked in __post_init__)
    for atomic_chunk in atomic_chunks:
        assert atomic_chunk.parsed_content is not None
        # The __post_init__ validation will raise if not contiguous
        assert atomic_chunk.old_start is not None
        assert atomic_chunk.new_start is not None
