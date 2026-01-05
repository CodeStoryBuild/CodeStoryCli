from unittest.mock import MagicMock, patch

import pytest

from codestory.core.diff.data.atomic_container import AtomicContainer
from codestory.core.diff.data.composite_container import CompositeContainer
from codestory.core.diff.data.standard_diff_chunk import StandardDiffChunk
from codestory.core.semantic_analysis.annotation.context_manager import ContextManager
from codestory.core.semantic_analysis.grouping.semantic_grouper import SemanticGrouper

# -------------------------------------------------------------------------
# Test Helpers
# -------------------------------------------------------------------------


def make_container(
    file_path: bytes, start_line: int, abs_new_line_start: int, is_context: bool = False
):
    """Creates a mock AtomicContainer with one mocked StandardDiffChunk."""
    chunk = MagicMock(spec=StandardDiffChunk)
    chunk.old_file_path = file_path
    chunk.new_file_path = file_path  # simplify for modification
    chunk.new_hash = "hash"
    chunk.old_start = start_line

    # Mock sort key: (old_start, min_abs_new_line)
    chunk.get_sort_key.return_value = (start_line, abs_new_line_start)
    chunk.line_anchor = start_line

    # Mock methods needed for grouping interactions if any
    chunk.canonical_path.return_value = file_path
    chunk.get_atomic_chunks.return_value = [chunk]

    container = MagicMock(spec=AtomicContainer)
    container.get_atomic_chunks.return_value = [chunk]
    container.canonical_paths.return_value = [file_path]

    # We will patch _is_context_container to look for this attribute
    # to avoid complex mocking of ContextManager/CommentMap in these logic tests
    container._test_is_context = is_context
    container._test_id = f"{file_path.decode()}:{start_line}"

    return container


@pytest.fixture
def mock_context_manager():
    return MagicMock(spec=ContextManager)


@pytest.fixture
def grouper(mock_context_manager):
    return SemanticGrouper(context_manager=mock_context_manager)


# -------------------------------------------------------------------------
# Tests
# -------------------------------------------------------------------------


class TestContextGrouping:
    def test_group_context_chunks_below(self, grouper):
        """Test attaching context to the chunk immediately below it."""
        # [Context]
        # [Code]
        c1 = make_container(b"A.py", 10, 10, is_context=True)
        c2 = make_container(b"A.py", 20, 20, is_context=False)

        # Patch the identification method to use our flag
        with patch.object(
            SemanticGrouper,
            "_is_context_container",
            side_effect=lambda c: getattr(c, "_test_is_context", False),
        ):
            results = grouper._group_context_chunks([c1, c2])

        assert len(results) == 1
        assert isinstance(results[0], CompositeContainer)
        # Should contain both, valid order (preserved)
        # CompositeContainer stores containers in .containers
        assert results[0].containers == [c1, c2]

    def test_group_context_chunks_above(self, grouper):
        """Test attaching context to the chunk above if none below."""
        # [Code]
        # [Context] (trailing)
        c1 = make_container(b"A.py", 10, 10, is_context=False)
        c2 = make_container(b"A.py", 20, 20, is_context=True)

        with patch.object(
            SemanticGrouper,
            "_is_context_container",
            side_effect=lambda c: getattr(c, "_test_is_context", False),
        ):
            results = grouper._group_context_chunks([c1, c2])

        assert len(results) == 1
        assert isinstance(results[0], CompositeContainer)
        assert results[0].containers == [c1, c2]

    def test_group_context_sandwiched(self, grouper):
        """Test context sandwiched between code prefers below."""
        # [Code1]
        # [Context]
        # [Code2]
        c1 = make_container(b"A.py", 10, 10, is_context=False)
        c2 = make_container(b"A.py", 20, 20, is_context=True)
        c3 = make_container(b"A.py", 30, 30, is_context=False)

        with patch.object(
            SemanticGrouper,
            "_is_context_container",
            side_effect=lambda c: getattr(c, "_test_is_context", False),
        ):
            results = grouper._group_context_chunks([c1, c2, c3])

        assert len(results) == 2
        # c1 stays alone
        assert results[0] == c1
        # c2 attaches to c3
        assert isinstance(results[1], CompositeContainer)
        assert results[1].containers == [c2, c3]

    def test_group_consecutive_context(self, grouper):
        """Test multiple consecutive context chunks attach to same target."""
        # [Code1]
        # [Context1]
        # [Context2]
        # [Code2]
        c1 = make_container(b"A.py", 10, 10, is_context=False)
        c2 = make_container(b"A.py", 20, 20, is_context=True)
        c3 = make_container(b"A.py", 30, 30, is_context=True)
        c4 = make_container(b"A.py", 40, 40, is_context=False)

        with patch.object(
            SemanticGrouper,
            "_is_context_container",
            side_effect=lambda c: getattr(c, "_test_is_context", False),
        ):
            results = grouper._group_context_chunks([c1, c2, c3, c4])

        assert len(results) == 2
        assert results[0] == c1

        # c2, c3, c4 grouped
        assert isinstance(results[1], CompositeContainer)
        assert results[1].containers == [c2, c3, c4]

    def test_group_all_context(self, grouper):
        """Test all context chunks are grouped together."""
        c1 = make_container(b"A.py", 10, 10, is_context=True)
        c2 = make_container(b"A.py", 20, 20, is_context=True)

        with patch.object(
            SemanticGrouper,
            "_is_context_container",
            side_effect=lambda c: getattr(c, "_test_is_context", False),
        ):
            results = grouper._group_context_chunks([c1, c2])

        assert len(results) == 1
        assert isinstance(results[0], CompositeContainer)
        assert results[0].containers == [c1, c2]

    def test_group_mixed_files(self, grouper):
        """Test grouping does not cross file boundaries."""
        # File A: [Context]
        # File B: [Code]
        c1 = make_container(b"A.py", 10, 10, is_context=True)
        c2 = make_container(b"B.py", 10, 10, is_context=False)

        with patch.object(
            SemanticGrouper,
            "_is_context_container",
            side_effect=lambda c: getattr(c, "_test_is_context", False),
        ):
            results = grouper._group_context_chunks([c1, c2])

        # Should remain separate because different files
        assert len(results) == 2
        assert results[0] == c1
        assert results[1] == c2

    def test_sorting_by_anchor(self, grouper):
        """Test containers are sorted by line anchor before grouping."""
        # Input order: [Code(30)], [Context(20)]
        # Sorted: [Context(20)], [Code(30)] -> Grouped
        c1 = make_container(b"A.py", 30, 30, is_context=False)
        c2 = make_container(b"A.py", 20, 20, is_context=True)

        with patch.object(
            SemanticGrouper,
            "_is_context_container",
            side_effect=lambda c: getattr(c, "_test_is_context", False),
        ):
            results = grouper._group_context_chunks([c1, c2])

        # Should be sorted and grouped: [Composite(c2, c1)]
        assert len(results) == 1
        assert isinstance(results[0], CompositeContainer)
        assert results[0].containers == [c2, c1]
