import pytest
from unittest.mock import Mock, patch, MagicMock
from dslate.core.semantic_grouper.context_manager import ContextManager, AnalysisContext
from dslate.core.data.diff_chunk import DiffChunk
from dslate.core.file_reader.protocol import FileReader
from dslate.core.file_reader.file_parser import FileParser, ParsedFile
from dslate.core.semantic_grouper.query_manager import QueryManager

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def create_chunk(
    old_path=b"file.txt",
    new_path=b"file.txt",
    old_start=1,
    old_len=1,
    new_start=1,
    new_len=1,
    is_rename=False,
    is_add=False,
    is_del=False,
):
    chunk = Mock(spec=DiffChunk)
    chunk.canonical_path.return_value = new_path if not is_del else old_path
    chunk.old_file_path = old_path
    chunk.new_file_path = new_path
    chunk.old_start = old_start
    chunk.old_len.return_value = old_len
    chunk.get_abs_new_line_start.return_value = new_start
    chunk.get_abs_new_line_end.return_value = new_start + new_len - 1

    chunk.is_standard_modification = not (is_rename or is_add or is_del)
    chunk.is_file_rename = is_rename
    chunk.is_file_addition = is_add
    chunk.is_file_deletion = is_del

    return chunk


@pytest.fixture
def mocks():
    return {
        "parser": Mock(spec=FileParser),
        "reader": Mock(spec=FileReader),
        "qm": Mock(spec=QueryManager),
        "scope_mapper": Mock(),
        "symbol_mapper": Mock(),
        "symbol_extractor": Mock(),
        "comment_mapper": Mock(),
    }


@pytest.fixture
def context_manager_deps(mocks):
    with (
        patch(
            "dslate.core.semantic_grouper.context_manager.ScopeMapper",
            return_value=mocks["scope_mapper"],
        ),
        patch(
            "dslate.core.semantic_grouper.context_manager.SymbolMapper",
            return_value=mocks["symbol_mapper"],
        ),
        patch(
            "dslate.core.semantic_grouper.context_manager.SymbolExtractor",
            return_value=mocks["symbol_extractor"],
        ),
        patch(
            "dslate.core.semantic_grouper.context_manager.CommentMapper",
            return_value=mocks["comment_mapper"],
        ),
    ):
        yield mocks

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

def test_analyze_required_contexts_mod(context_manager_deps):
    chunk = create_chunk()
    cm = ContextManager(
        context_manager_deps["parser"],
        context_manager_deps["reader"],
        context_manager_deps["qm"],
        [chunk],
    )

    req = cm.get_required_contexts()
    assert (b"file.txt", True) in req
    assert (b"file.txt", False) in req

def test_analyze_required_contexts_add(context_manager_deps):
    chunk = create_chunk(is_add=True, old_path=None)
    cm = ContextManager(
        context_manager_deps["parser"],
        context_manager_deps["reader"],
        context_manager_deps["qm"],
        [chunk],
    )

    req = cm.get_required_contexts()
    assert (b"file.txt", False) in req
    assert (b"file.txt", True) not in req

def test_analyze_required_contexts_del(context_manager_deps):
    chunk = create_chunk(is_del=True, new_path=None)
    cm = ContextManager(
        context_manager_deps["parser"],
        context_manager_deps["reader"],
        context_manager_deps["qm"],
        [chunk],
    )

    req = cm.get_required_contexts()
    assert (b"file.txt", True) in req
    assert (b"file.txt", False) not in req


def test_simplify_overlapping_ranges(context_manager_deps):
    # We can test this static-like method by instantiating with empty chunks
    cm = ContextManager(
        context_manager_deps["parser"],
        context_manager_deps["reader"],
        context_manager_deps["qm"],
        [],
    )

    ranges = [(1, 5), (3, 7), (10, 12)]
    simplified = cm.simplify_overlapping_ranges(ranges)

    # (1, 5) and (3, 7) overlap -> (1, 7)
    # (10, 12) is separate
    assert simplified == [(1, 7), (10, 12)]

    # Touching ranges
    ranges_touching = [(1, 5), (6, 10)]
    simplified_touching = cm.simplify_overlapping_ranges(ranges_touching)
    # (1, 5) ends at 5. (6, 10) starts at 6. 5 >= 6-1 (5 >= 5) -> True. Merge.
    assert simplified_touching == [(1, 10)]

def test_build_context_success(context_manager_deps):
    chunk = create_chunk()

    # Setup mocks for successful build
    context_manager_deps["reader"].read.return_value = "content"

    parsed_file = Mock()
    parsed_file.root_node.has_error = False
    parsed_file.detected_language = "python"
    parsed_file.content_bytes = b"content"
    parsed_file.line_ranges = []

    context_manager_deps["parser"].parse_file.return_value = parsed_file

    # Config for shared tokens
    config = Mock()
    config.share_tokens_between_files = False
    context_manager_deps["qm"].get_config.return_value = config

    context_manager_deps["symbol_extractor"].extract_defined_symbols.return_value = {
        "sym"
    }
    context_manager_deps["scope_mapper"].build_scope_map.return_value = Mock()
    context_manager_deps["symbol_mapper"].build_symbol_map.return_value = Mock()
    context_manager_deps["comment_mapper"].build_comment_map.return_value = Mock()

    cm = ContextManager(
        context_manager_deps["parser"],
        context_manager_deps["reader"],
        context_manager_deps["qm"],
        [chunk],
    )

    assert cm.has_context(b"file.txt", True)
    assert cm.has_context(b"file.txt", False)

    ctx = cm.get_context(b"file.txt", True)
    assert isinstance(ctx, AnalysisContext)
    assert ctx.file_path == b"file.txt"
    assert ctx.is_old_version is True

def test_build_context_syntax_error(context_manager_deps):
    chunk = create_chunk()

    context_manager_deps["reader"].read.return_value = "content"

    parsed_file = Mock()
    parsed_file.root_node.has_error = True  # Syntax error
    parsed_file.detected_language = "python"

    context_manager_deps["parser"].parse_file.return_value = parsed_file

    cm = ContextManager(
        context_manager_deps["parser"],
        context_manager_deps["reader"],
        context_manager_deps["qm"],
        [chunk],
    )

    # Should not have context due to syntax error
    assert not cm.has_context(b"file.txt", True)
