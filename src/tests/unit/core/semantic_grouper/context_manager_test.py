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

from unittest.mock import Mock, patch

import pytest

from codestory.core.data.diff_chunk import DiffChunk
from codestory.core.file_reader.protocol import FileReader
from codestory.core.semantic_grouper.context_manager import (
    AnalysisContext,
    ContextManager,
)
from codestory.core.semantic_grouper.query_manager import QueryManager

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
    chunk.get_chunks = Mock(return_value=[chunk])

    return chunk


@pytest.fixture
def mocks():
    return {
        "reader": Mock(spec=FileReader),
        "scope_mapper": Mock(),
        "symbol_mapper": Mock(),
        "symbol_extractor": Mock(),
        "comment_mapper": Mock(),
    }


@pytest.fixture
def context_manager_deps(mocks):
    query_mgr = Mock(spec=QueryManager)
    # Default to returning None for parse; tests will override where needed
    with (
        patch(
            "codestory.core.semantic_grouper.context_manager.ScopeMapper",
            return_value=mocks["scope_mapper"],
        ),
        patch(
            "codestory.core.semantic_grouper.context_manager.SymbolMapper",
            return_value=mocks["symbol_mapper"],
        ),
        patch(
            "codestory.core.semantic_grouper.context_manager.SymbolExtractor",
            return_value=mocks["symbol_extractor"],
        ),
        patch(
            "codestory.core.semantic_grouper.context_manager.CommentMapper",
            return_value=mocks["comment_mapper"],
        ),
        patch(
            "codestory.core.semantic_grouper.context_manager.QueryManager.get_instance",
            return_value=query_mgr,
        ),
        patch(
            "codestory.core.semantic_grouper.context_manager.FileParser.parse_file",
            autospec=True,
        ) as parse_file_patch,
    ):
        # include the patched instances for tests
        mocks.update(
            {
                "query_manager": query_mgr,
                "file_parser_parse": parse_file_patch,
            }
        )
        yield mocks


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


def test_analyze_required_contexts_mod(context_manager_deps):
    chunk = create_chunk()
    cm = ContextManager([chunk], context_manager_deps["reader"], False)

    req = cm.get_required_contexts()
    assert (b"file.txt", True) in req
    assert (b"file.txt", False) in req


def test_analyze_required_contexts_add(context_manager_deps):
    chunk = create_chunk(is_add=True, old_path=None)
    cm = ContextManager([chunk], context_manager_deps["reader"], False)

    req = cm.get_required_contexts()
    assert (b"file.txt", False) in req
    assert (b"file.txt", True) not in req


def test_analyze_required_contexts_del(context_manager_deps):
    chunk = create_chunk(is_del=True, new_path=None)
    cm = ContextManager([chunk], context_manager_deps["reader"], False)

    req = cm.get_required_contexts()
    assert (b"file.txt", True) in req
    assert (b"file.txt", False) not in req


def test_simplify_overlapping_ranges(context_manager_deps):
    # We can test this static-like method by instantiating with empty chunks
    cm = ContextManager([], context_manager_deps["reader"], False)

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
    parsed_file.root_node.children = []
    parsed_file.detected_language = "python"
    parsed_file.content_bytes = b"content"
    parsed_file.line_ranges = []

    # Config for shared tokens
    config = Mock()
    config.share_tokens_between_files = False
    # Make QueryManager.get_instance() return a qmgr whose get_config returns config
    context_manager_deps["query_manager"].get_config.return_value = config

    context_manager_deps["symbol_extractor"].extract_defined_symbols.return_value = {
        "sym"
    }
    context_manager_deps["scope_mapper"].build_scope_map.return_value = Mock()
    context_manager_deps["symbol_mapper"].build_symbol_map.return_value = Mock()
    context_manager_deps["comment_mapper"].build_comment_map.return_value = Mock()

    # Patch parse to return the mocked parsed_file
    context_manager_deps["file_parser_parse"].return_value = parsed_file

    cm = ContextManager([chunk], context_manager_deps["reader"], False)

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
    parsed_file.content_bytes = b"content"
    parsed_file.line_ranges = []

    # Make QueryManager return a harmless config
    cfg = Mock()
    cfg.share_tokens_between_files = False
    context_manager_deps["query_manager"].get_config.return_value = cfg

    # Patch parse to return our parsed_file with a syntax error
    context_manager_deps["file_parser_parse"].return_value = parsed_file

    # When fail_on_syntax_errors=False, the manager should still create contexts (it logs a warning)
    cm = ContextManager(
        [chunk],
        context_manager_deps["reader"],
        False,
    )

    assert cm.has_context(b"file.txt", True)
    assert cm.has_context(b"file.txt", False)

    # When fail_on_syntax_errors=True, constructing the manager should raise SyntaxErrorDetected
    from codestory.core.exceptions import SyntaxErrorDetected

    with pytest.raises(SyntaxErrorDetected):
        ContextManager(
            [chunk],
            context_manager_deps["reader"],
            True,
        )
