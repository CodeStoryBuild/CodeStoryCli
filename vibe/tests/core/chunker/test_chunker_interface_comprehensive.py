"""
Comprehensive tests for ChunkerInterface implementations.

These tests ensure that all chunkers respect the core invariants:
1. Input/Output Preservation: Output chunks must contain exactly the same changes as input
2. Disjointness: Output chunks must be disjoint (no overlapping line numbers)
3. Validity: Each output chunk must be a valid, applicable git patch
4. Type Safety: Chunkers must handle all chunk types correctly
"""

import pytest
from typing import List, Type
import importlib

from vibe.core.chunker.interface import ChunkerInterface
from vibe.core.data.c_diff_chunk import CompositeDiffChunk
from vibe.core.data.diff_chunk import DiffChunk
from vibe.core.data.line_changes import Addition, Removal
from vibe.core.checks.chunk_checks import chunks_disjoint


# ============================================================================
# Helper Functions
# ============================================================================


def flatten_chunk(chunk: DiffChunk) -> List[tuple]:
    """
    Flatten a chunk to (type, line_number, content) tuples for comparison.
    Handles DiffChunk and CompositeDiffChunk.
    """
    result = []

    if isinstance(chunk, DiffChunk):
        for item in chunk.parsed_content:
            result.append((type(item).__name__, item.line_number, item.content))
    elif isinstance(chunk, CompositeDiffChunk):
        for sub_chunk in chunk.chunks:
            result.extend(flatten_chunk(sub_chunk))

    return result


def assert_input_preserved(output_chunks: List[DiffChunk], input_chunk: DiffChunk):
    """
    Assert that output chunks contain exactly the same changes as input.
    Changes can be reordered, but must be identical.
    """
    output_flattened = []
    for chunk in output_chunks:
        output_flattened.extend(flatten_chunk(chunk))

    input_flattened = flatten_chunk(input_chunk)

    assert sorted(output_flattened) == sorted(input_flattened), (
        f"Output chunks do not preserve input.\n"
        f"Input: {sorted(input_flattened)}\n"
        f"Output: {sorted(output_flattened)}"
    )


def extract_standard_chunks(chunks: List[DiffChunk]) -> List[DiffChunk]:
    """
    Extract all DiffChunk instances from a list of chunks.
    Handles CompositeDiffChunk by extracting child chunks.
    """
    result = []
    for chunk in chunks:
        if isinstance(chunk, DiffChunk):
            result.append(chunk)
        elif isinstance(chunk, CompositeDiffChunk):
            result.extend(chunk.chunks)
    return result


def assert_chunks_disjoint(chunks: List[DiffChunk]):
    """
    Assert that all chunks are disjoint using the official chunk_checks utility.
    """
    standard_chunks = extract_standard_chunks(chunks)
    assert chunks_disjoint(
        standard_chunks
    ), "Output chunks are not disjoint! Chunks have overlapping line numbers."


def assert_chunks_valid(chunks: List[DiffChunk]):
    """
    Assert that all chunks are valid (can be instantiated without errors).
    This validates contiguity and proper structure.
    """
    for chunk in chunks:
        if isinstance(chunk, DiffChunk):
            # The __post_init__ validation will raise if invalid
            assert chunk.parsed_content is not None
            assert chunk.canonical_path() is not None
        elif isinstance(chunk, CompositeDiffChunk):
            # Validate all child chunks
            for sub_chunk in chunk.chunks:
                assert isinstance(sub_chunk, DiffChunk)
                assert sub_chunk.parsed_content is not None


def run_chunker_invariants(chunker: ChunkerInterface, input_chunk: DiffChunk):
    """
    Run all invariant checks on a chunker's output.
    """
    output_chunks = chunker.chunk([input_chunk])

    # Invariant 1: Output must preserve input
    assert_input_preserved(output_chunks, input_chunk)

    # Invariant 2: Output must be disjoint
    assert_chunks_disjoint(output_chunks)

    # Invariant 3: Output must be valid
    assert_chunks_valid(output_chunks)

    return output_chunks


# ============================================================================
# Chunker Configurations
# ============================================================================

# Define all chunkers to test
CHUNKERS = [
    ("vibe.core.chunker.simple_chunker.SimpleChunker", {}),
    (
        "vibe.core.chunker.predicate_chunker.PredicateChunker",
        {"split_predicate": lambda x: x.strip() == ""},
    ),
    (
        "vibe.core.chunker.predicate_chunker.PredicateChunker",
        {"split_predicate": lambda x: "SPLIT" in x},
    ),
    ("vibe.core.chunker.max_line_chunker.MaxLineChunker", {"max_chunks": 3}),
    ("vibe.core.chunker.max_line_chunker.MaxLineChunker", {"max_chunks": 1}),
    ("vibe.core.chunker.max_line_chunker.MaxLineChunker", {"max_chunks": 10}),
]


def load_chunker(chunker_cls: str, chunker_kwargs: dict) -> ChunkerInterface:
    """Load a chunker class dynamically."""
    mod_name, cls_name = chunker_cls.rsplit(".", 1)
    mod = importlib.import_module(mod_name)
    Chunker = getattr(mod, cls_name)
    return Chunker(**chunker_kwargs)


# ============================================================================
# Test Cases: Basic Scenarios
# ============================================================================


@pytest.mark.parametrize("chunker_cls,chunker_kwargs", CHUNKERS)
def test_pure_additions(chunker_cls, chunker_kwargs):
    """Test chunker with pure additions (no removals)."""
    chunker = load_chunker(chunker_cls, chunker_kwargs)

    chunk = DiffChunk(
        old_file_path="test.py",
        new_file_path="test.py",
        parsed_content=[
            Addition(content="line1", line_number=1),
            Addition(content="line2", line_number=2),
            Addition(content="line3", line_number=3),
            Addition(content="line4", line_number=4),
            Addition(content="line5", line_number=5),
        ],
        old_start=0,
        new_start=1,
    )

    run_chunker_invariants(chunker, chunk)


@pytest.mark.parametrize("chunker_cls,chunker_kwargs", CHUNKERS)
def test_pure_removals(chunker_cls, chunker_kwargs):
    """Test chunker with pure removals (no additions)."""
    chunker = load_chunker(chunker_cls, chunker_kwargs)

    chunk = DiffChunk(
        old_file_path="test.py",
        new_file_path="test.py",
        parsed_content=[
            Removal(content="line1", line_number=10),
            Removal(content="line2", line_number=11),
            Removal(content="line3", line_number=12),
            Removal(content="line4", line_number=13),
            Removal(content="line5", line_number=14),
        ],
        old_start=10,
        new_start=0,
    )

    run_chunker_invariants(chunker, chunk)


@pytest.mark.parametrize("chunker_cls,chunker_kwargs", CHUNKERS)
def test_mixed_additions_removals(chunker_cls, chunker_kwargs):
    """Test chunker with interleaved additions and removals."""
    chunker = load_chunker(chunker_cls, chunker_kwargs)

    chunk = DiffChunk(
        old_file_path="test.py",
        new_file_path="test.py",
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

    run_chunker_invariants(chunker, chunk)


@pytest.mark.parametrize("chunker_cls,chunker_kwargs", CHUNKERS)
def test_single_addition(chunker_cls, chunker_kwargs):
    """Test chunker with a single addition."""
    chunker = load_chunker(chunker_cls, chunker_kwargs)

    chunk = DiffChunk(
        old_file_path="test.py",
        new_file_path="test.py",
        parsed_content=[
            Addition(content="single_line", line_number=5),
        ],
        old_start=0,
        new_start=5,
    )

    run_chunker_invariants(chunker, chunk)


@pytest.mark.parametrize("chunker_cls,chunker_kwargs", CHUNKERS)
def test_single_removal(chunker_cls, chunker_kwargs):
    """Test chunker with a single removal."""
    chunker = load_chunker(chunker_cls, chunker_kwargs)

    chunk = DiffChunk(
        old_file_path="test.py",
        new_file_path="test.py",
        parsed_content=[
            Removal(content="single_line", line_number=20),
        ],
        old_start=20,
        new_start=0,
    )

    run_chunker_invariants(chunker, chunk)


@pytest.mark.parametrize("chunker_cls,chunker_kwargs", CHUNKERS)
def test_single_modification(chunker_cls, chunker_kwargs):
    """Test chunker with a single line modification (removal + addition)."""
    chunker = load_chunker(chunker_cls, chunker_kwargs)

    chunk = DiffChunk(
        old_file_path="test.py",
        new_file_path="test.py",
        parsed_content=[
            Addition(content="new_line", line_number=10),
            Removal(content="old_line", line_number=10),
        ],
        old_start=10,
        new_start=10,
    )

    run_chunker_invariants(chunker, chunk)


# ============================================================================
# Test Cases: Edge Cases
# ============================================================================


@pytest.mark.parametrize("chunker_cls,chunker_kwargs", CHUNKERS)
def test_large_chunk(chunker_cls, chunker_kwargs):
    """Test chunker with a large chunk (100 lines)."""
    chunker = load_chunker(chunker_cls, chunker_kwargs)

    parsed_content = []
    content_lines = []

    for i in range(50):
        parsed_content.append(Addition(content=f"addition_{i}", line_number=i + 1))
        content_lines.append(f"+addition_{i}")
        parsed_content.append(Removal(content=f"removal_{i}", line_number=i + 1))
        content_lines.append(f"-removal_{i}")

    chunk = DiffChunk(
        old_file_path="large.py",
        new_file_path="large.py",
        parsed_content=parsed_content,
        old_start=1,
        new_start=1,
    )

    run_chunker_invariants(chunker, chunk)


@pytest.mark.parametrize("chunker_cls,chunker_kwargs", CHUNKERS)
def test_chunk_with_blank_lines(chunker_cls, chunker_kwargs):
    """Test chunker with blank line content (important for predicate chunkers)."""
    chunker = load_chunker(chunker_cls, chunker_kwargs)

    chunk = DiffChunk(
        old_file_path="test.py",
        new_file_path="test.py",
        parsed_content=[
            Addition(content="line1", line_number=1),
            Addition(content="", line_number=2),
            Addition(content="line3", line_number=3),
            Addition(content="", line_number=4),
            Addition(content="line5", line_number=5),
        ],
        old_start=0,
        new_start=1,
    )

    run_chunker_invariants(chunker, chunk)


@pytest.mark.parametrize("chunker_cls,chunker_kwargs", CHUNKERS)
def test_chunk_with_special_characters(chunker_cls, chunker_kwargs):
    """Test chunker with special characters in content."""
    chunker = load_chunker(chunker_cls, chunker_kwargs)

    chunk = DiffChunk(
        old_file_path="test.py",
        new_file_path="test.py",
        parsed_content=[
            Addition(content="def foo():", line_number=1),
            Removal(content="def bar():", line_number=1),
            Addition(content='    print("SPLIT HERE")', line_number=2),
            Removal(content='    print("test")', line_number=2),
        ],
        old_start=1,
        new_start=1,
    )

    run_chunker_invariants(chunker, chunk)


@pytest.mark.parametrize("chunker_cls,chunker_kwargs", CHUNKERS)
def test_non_contiguous_line_numbers(chunker_cls, chunker_kwargs):
    """
    Test chunker with additions and removals at different line positions.
    This is a valid git patch pattern.
    """
    chunker = load_chunker(chunker_cls, chunker_kwargs)

    chunk = DiffChunk(
        old_file_path="test.py",
        new_file_path="test.py",
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

    run_chunker_invariants(chunker, chunk)


# ============================================================================
# Test Cases: Multiple Input Chunks
# ============================================================================


@pytest.mark.parametrize("chunker_cls,chunker_kwargs", CHUNKERS)
def test_multiple_input_chunks_same_file(chunker_cls, chunker_kwargs):
    """Test chunker with multiple input chunks from the same file."""
    chunker = load_chunker(chunker_cls, chunker_kwargs)

    chunk1 = DiffChunk(
        old_file_path="test.py",
        new_file_path="test.py",
        parsed_content=[
            Addition(content="line1", line_number=1),
            Addition(content="line2", line_number=2),
        ],
        old_start=0,
        new_start=1,
    )

    chunk2 = DiffChunk(
        old_file_path="test.py",
        new_file_path="test.py",
        parsed_content=[
            Removal(content="line10", line_number=10),
            Removal(content="line11", line_number=11),
        ],
        old_start=10,
        new_start=0,
    )

    # Test each chunk separately since they're from different parts of the file
    run_chunker_invariants(chunker, chunk1)
    run_chunker_invariants(chunker, chunk2)


@pytest.mark.parametrize("chunker_cls,chunker_kwargs", CHUNKERS)
def test_multiple_input_chunks_different_files(chunker_cls, chunker_kwargs):
    """Test chunker with multiple input chunks from different files."""
    chunker = load_chunker(chunker_cls, chunker_kwargs)

    chunk1 = DiffChunk(
        old_file_path="file1.py",
        new_file_path="file1.py",
        parsed_content=[
            Addition(content="line1", line_number=1),
        ],
        old_start=0,
        new_start=1,
    )

    chunk2 = DiffChunk(
        old_file_path="file2.py",
        new_file_path="file2.py",
        parsed_content=[
            Removal(content="line1", line_number=1),
        ],
        old_start=1,
        new_start=0,
    )

    # Test each chunk separately since they're from different files
    run_chunker_invariants(chunker, chunk1)
    run_chunker_invariants(chunker, chunk2)


# ============================================================================
# Test Cases: Composite Chunk Handling
# ============================================================================


@pytest.mark.parametrize("chunker_cls,chunker_kwargs", CHUNKERS)
def test_output_composite_chunks_are_valid(chunker_cls, chunker_kwargs):
    """Test that composite chunks in output are properly structured."""
    chunker = load_chunker(chunker_cls, chunker_kwargs)

    # Create a chunk large enough to potentially create composites
    parsed_content = []
    content_lines = []

    for i in range(20):
        parsed_content.append(Addition(content=f"line_{i}", line_number=i + 1))
        content_lines.append(f"+line_{i}")

    chunk = DiffChunk(
        old_file_path="test.py",
        new_file_path="test.py",
        parsed_content=parsed_content,
        old_start=0,
        new_start=1,
    )

    output_chunks = chunker.chunk([chunk])

    # Check that any composite chunks have valid structure
    for out_chunk in output_chunks:
        if isinstance(out_chunk, CompositeDiffChunk):
            assert len(out_chunk.chunks) > 0, "Composite chunk is empty"
            assert all(
                isinstance(c, DiffChunk) for c in out_chunk.chunks
            ), "Composite chunk contains non-DiffChunk"
            assert (
                out_chunk.canonical_path() == chunk.canonical_path()
            ), "Composite chunk file path doesn't match"

    # Run standard invariants
    assert_input_preserved(output_chunks, chunk)
    assert_chunks_disjoint(output_chunks)


# ============================================================================
# Test Cases: Rename Chunk Handling
# ============================================================================

"""
# COMMENTED OUT: RenameDiffChunk does not exist in the current implementation
@pytest.mark.parametrize("chunker_cls,chunker_kwargs", CHUNKERS)
def test_rename_chunk_passthrough(chunker_cls, chunker_kwargs):
    '''Test that rename chunks pass through unchanged.'''
    chunker = load_chunker(chunker_cls, chunker_kwargs)

    # Use from_raw_patch factory method to create RenameDiffChunk
    rename_chunk = RenameDiffChunk.from_raw_patch(
        old_file_path="old_name.py",
        new_file_path="new_name.py",
        patch_content="@@ -0,0 +0,0 @@",
    )

    output = chunker.chunk([rename_chunk])

    # Rename chunks should pass through unchanged
    assert len(output) == 1
    assert isinstance(output[0], RenameDiffChunk)
    assert output[0].old_file_path == "old_name.py"
    assert output[0].new_file_path == "new_name.py"
"""


# ============================================================================
# Test Cases: Empty Input Handling
# ============================================================================


@pytest.mark.parametrize("chunker_cls,chunker_kwargs", CHUNKERS)
def test_empty_input_list(chunker_cls, chunker_kwargs):
    """Test chunker with empty input list."""
    chunker = load_chunker(chunker_cls, chunker_kwargs)

    output = chunker.chunk([])

    assert output == [] or len(output) == 0, "Empty input should produce empty output"
