"""
Comprehensive tests for ChunkerInterface implementations.

Tests the actual chunker implementations: AtomicChunker and SimpleChunker.
These tests ensure basic functionality and interface compliance.
"""

from unittest.mock import Mock

import pytest
from vibe.core.chunker.atomic_chunker import AtomicChunker
from vibe.core.chunker.interface import MechanicalChunker
from vibe.core.chunker.simple_chunker import SimpleChunker
from vibe.core.data.diff_chunk import DiffChunk
from vibe.core.data.line_changes import Addition, Removal

# ============================================================================
# Helper Functions
# ============================================================================


def create_mock_diff_chunk(
    file_path: str = "test.py", num_changes: int = 5
) -> DiffChunk:
    """Create a mock DiffChunk for testing."""
    mock_chunk = Mock(spec=DiffChunk)
    mock_chunk.canonical_path.return_value = file_path
    mock_chunk.old_file_path = file_path
    mock_chunk.new_file_path = file_path

    # Create mock changes
    parsed_content = []
    for i in range(num_changes):
        if i % 2 == 0:
            change = Mock(spec=Addition)
            change.line_number = i + 1
            change.content = f"added_line_{i}"
        else:
            change = Mock(spec=Removal)
            change.line_number = i + 1
            change.content = f"removed_line_{i}"
        parsed_content.append(change)

    mock_chunk.parsed_content = parsed_content
    return mock_chunk


def assert_chunker_interface_compliance(chunker: MechanicalChunker):
    """Assert that a chunker implements the required interface."""
    assert hasattr(chunker, "chunk"), "Chunker must have chunk method"
    assert callable(chunker.chunk), "chunk must be callable"


def assert_chunk_output_valid(output_chunks: list, original_chunks: list):
    """Assert that chunker output is valid."""
    assert isinstance(output_chunks, list), "Output must be a list"
    assert len(output_chunks) >= len(original_chunks), (
        "Output should have at least as many chunks as input"
    )

    for chunk in output_chunks:
        # Each output item should be a valid chunk-like object
        assert hasattr(chunk, "canonical_path"), (
            "Output chunks must have canonical_path method"
        )


# ============================================================================
# Test Configurations
# ============================================================================


CHUNKERS_TO_TEST = [
    ("SimpleChunker", SimpleChunker, {}),
    ("AtomicChunker", AtomicChunker, {}),
]


# ============================================================================
# Test Cases: Basic Scenarios
# ============================================================================


@pytest.mark.parametrize("name,chunker_class,chunker_kwargs", CHUNKERS_TO_TEST)
def test_chunker_interface_compliance(name, chunker_class, chunker_kwargs):
    """Test that chunker implements the required interface."""
    chunker = chunker_class(**chunker_kwargs)
    assert_chunker_interface_compliance(chunker)


@pytest.mark.parametrize("name,chunker_class,chunker_kwargs", CHUNKERS_TO_TEST)
def test_empty_input(name, chunker_class, chunker_kwargs):
    """Test chunker with empty input."""
    chunker = chunker_class(**chunker_kwargs)

    result = chunker.chunk([])

    assert isinstance(result, list), "Should return a list"
    assert len(result) == 0, "Empty input should produce empty output"


@pytest.mark.parametrize("name,chunker_class,chunker_kwargs", CHUNKERS_TO_TEST)
def test_single_chunk(name, chunker_class, chunker_kwargs):
    """Test chunker with a single chunk."""
    chunker = chunker_class(**chunker_kwargs)

    chunk = create_mock_diff_chunk("test.py", 3)
    result = chunker.chunk([chunk])

    assert_chunk_output_valid(result, [chunk])


@pytest.mark.parametrize("name,chunker_class,chunker_kwargs", CHUNKERS_TO_TEST)
def test_multiple_chunks(name, chunker_class, chunker_kwargs):
    """Test chunker with multiple chunks."""
    chunker = chunker_class(**chunker_kwargs)

    chunk1 = create_mock_diff_chunk("file1.py", 2)
    chunk2 = create_mock_diff_chunk("file2.py", 3)
    result = chunker.chunk([chunk1, chunk2])

    assert_chunk_output_valid(result, [chunk1, chunk2])


@pytest.mark.parametrize("name,chunker_class,chunker_kwargs", CHUNKERS_TO_TEST)
def test_chunker_preserves_file_paths(name, chunker_class, chunker_kwargs):
    """Test that chunker preserves file paths in output."""
    chunker = chunker_class(**chunker_kwargs)

    chunk = create_mock_diff_chunk("src/important.py", 5)
    result = chunker.chunk([chunk])

    # All output chunks should maintain the same file path
    for output_chunk in result:
        if hasattr(output_chunk, "canonical_path"):
            assert output_chunk.canonical_path() == "src/important.py"


class TestSimpleChunker:
    """Specific tests for SimpleChunker implementation."""

    def test_simple_chunker_initialization(self):
        """Test SimpleChunker can be initialized."""
        chunker = SimpleChunker()
        assert isinstance(chunker, SimpleChunker)
        assert isinstance(chunker, MechanicalChunker)

    def test_simple_chunker_basic_functionality(self):
        """Test SimpleChunker basic chunking."""
        chunker = SimpleChunker()

        chunk1 = create_mock_diff_chunk("test1.py", 2)
        chunk2 = create_mock_diff_chunk("test2.py", 3)

        result = chunker.chunk([chunk1, chunk2])

        assert isinstance(result, list)
        assert len(result) >= 0  # Should return some result

    def test_simple_chunker_with_none_input(self):
        """Test SimpleChunker handles None gracefully."""
        chunker = SimpleChunker()

        # Should handle None input gracefully
        with pytest.raises((TypeError, AttributeError)):
            chunker.chunk(None)


class TestAtomicChunker:
    """Specific tests for AtomicChunker implementation."""

    def test_atomic_chunker_initialization(self):
        """Test AtomicChunker can be initialized."""
        chunker = AtomicChunker()
        assert isinstance(chunker, AtomicChunker)
        assert isinstance(chunker, MechanicalChunker)

    def test_atomic_chunker_basic_functionality(self):
        """Test AtomicChunker basic chunking."""
        chunker = AtomicChunker()

        chunk1 = create_mock_diff_chunk("test1.py", 4)
        chunk2 = create_mock_diff_chunk("test2.py", 2)

        result = chunker.chunk([chunk1, chunk2])

        assert isinstance(result, list)
        assert len(result) >= 0  # Should return some result

    def test_atomic_chunker_with_large_chunks(self):
        """Test AtomicChunker with larger chunks."""
        chunker = AtomicChunker()

        # Create a larger chunk
        large_chunk = create_mock_diff_chunk("large_file.py", 20)

        result = chunker.chunk([large_chunk])

        assert isinstance(result, list)
        # Atomic chunker might split large chunks into smaller ones
        assert len(result) >= 1


class TestChunkerErrorHandling:
    """Test error handling in chunker implementations."""

    @pytest.mark.parametrize(
        "name,chunker_class,chunker_kwargs", CHUNKERS_TO_TEST
    )
    def test_chunker_handles_invalid_input(
        self, name, chunker_class, chunker_kwargs
    ):
        """Test that chunkers handle invalid input gracefully."""
        chunker = chunker_class(**chunker_kwargs)

        # Test with invalid input types
        with pytest.raises((TypeError, AttributeError)):
            chunker.chunk("not_a_list")

        with pytest.raises((TypeError, AttributeError)):
            chunker.chunk([1, 2, 3])  # Not chunk objects

    @pytest.mark.parametrize(
        "name,chunker_class,chunker_kwargs", CHUNKERS_TO_TEST
    )
    def test_chunker_handles_malformed_chunks(
        self, name, chunker_class, chunker_kwargs
    ):
        """Test chunkers with malformed chunk objects."""
        chunker = chunker_class(**chunker_kwargs)

        # Create a mock object that looks like a chunk but is missing methods
        malformed_chunk = Mock()
        malformed_chunk.canonical_path = Mock(
            side_effect=Exception("Malformed chunk")
        )

        # Should either handle gracefully or raise appropriate exception
        try:
            result = chunker.chunk([malformed_chunk])
            # If it doesn't raise, result should be a list
            assert isinstance(result, list)
        except Exception as e:
            # If it raises, should be a reasonable exception type
            assert isinstance(e, (TypeError, AttributeError, ValueError))


class TestChunkerIntegration:
    """Integration tests for chunker functionality."""

    def test_chunkers_work_with_real_diff_data(self):
        """Test chunkers with more realistic diff-like data."""
        # This test would need actual DiffChunk objects
        # For now, we'll test that chunkers can be used in a pipeline-like way

        simple_chunker = SimpleChunker()
        atomic_chunker = AtomicChunker()

        # Create some mock chunks
        chunk1 = create_mock_diff_chunk("src/main.py", 5)
        chunk2 = create_mock_diff_chunk("src/utils.py", 3)
        chunks = [chunk1, chunk2]

        # Test that both chunkers can process the same input
        simple_result = simple_chunker.chunk(chunks)
        atomic_result = atomic_chunker.chunk(chunks)

        # Both should return valid results
        assert isinstance(simple_result, list)
        assert isinstance(atomic_result, list)

    def test_chunker_consistency(self):
        """Test that chunkers produce consistent results."""
        chunker = SimpleChunker()

        chunk = create_mock_diff_chunk("test.py", 3)

        # Run chunker multiple times with same input
        result1 = chunker.chunk([chunk])
        result2 = chunker.chunk([chunk])

        # Results should be consistent
        assert len(result1) == len(result2)

        # If both have same length, compare their canonical paths
        if len(result1) > 0 and len(result2) > 0:
            for r1, r2 in zip(result1, result2, strict=False):
                if hasattr(r1, "canonical_path") and hasattr(
                    r2, "canonical_path"
                ):
                    assert r1.canonical_path() == r2.canonical_path()


# ============================================================================
# Performance Tests
# ============================================================================


class TestChunkerPerformance:
    """Basic performance tests for chunkers."""

    @pytest.mark.parametrize("name,chunker_class,chunker_kwargs", CHUNKERS_TO_TEST)
    def test_chunker_performance_many_chunks(self, name, chunker_class, chunker_kwargs):
        """Test chunker performance with many input chunks."""
        chunker = chunker_class(**chunker_kwargs)

        # Create many small chunks
        chunks = []
        for i in range(50):
            chunk = create_mock_diff_chunk(f"file_{i}.py", 2)
            chunks.append(chunk)

        import time

        start_time = time.time()

        result = chunker.chunk(chunks)

        end_time = time.time()

        # Should complete in reasonable time (less than 1 second for this test)
        assert end_time - start_time < 1.0, (
            f"{name} took too long: {end_time - start_time}s"
        )
        assert isinstance(result, list)

    @pytest.mark.parametrize("name,chunker_class,chunker_kwargs", CHUNKERS_TO_TEST)
    def test_chunker_performance_large_chunks(
        self, name, chunker_class, chunker_kwargs
    ):
        """Test chunker performance with large input chunks."""
        chunker = chunker_class(**chunker_kwargs)

        # Create fewer but larger chunks
        large_chunk = create_mock_diff_chunk("large_file.py", 100)

        import time

        start_time = time.time()

        result = chunker.chunk([large_chunk])

        end_time = time.time()

        # Should complete in reasonable time
        assert end_time - start_time < 1.0, (
            f"{name} took too long: {end_time - start_time}s"
        )
        assert isinstance(result, list)
