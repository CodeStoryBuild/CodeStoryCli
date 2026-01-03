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

from codestory.core.diff.data.standard_diff_chunk import StandardDiffChunk
from codestory.core.semantic_analysis.annotation.context_manager import (
    AnalysisContext,
    ContextManagerBuilder,
)
from codestory.core.semantic_analysis.annotation.file_manager import FileManager
from codestory.core.semantic_analysis.mappers.query_manager import QueryManager

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
    from codestory.core.diff.data.line_changes import Addition, Removal

    parsed_content = []
    if is_add:
        parsed_content.append(Addition(0, new_start, b"new"))
    elif is_del:
        parsed_content.append(Removal(old_start, 0, b"old"))
    else:
        parsed_content.append(Removal(old_start, 0, b"old"))
        parsed_content.append(Addition(0, new_start, b"new"))

    chunk = StandardDiffChunk(
        base_hash="base",
        new_hash="patched",
        old_file_path=old_path if not is_add else None,
        new_file_path=new_path if not is_del else None,
        old_start=old_start if not is_add else None,
        parsed_content=parsed_content,
    )

    return chunk


@pytest.fixture
def mocks():
    symbol_extractor = Mock()
    symbol_extractor.extract_defined_symbols.return_value = set()

    scope_mapper = Mock()
    scope_mapper.build_scope_map.return_value = Mock()

    symbol_mapper = Mock()
    symbol_mapper.build_symbol_map.return_value = Mock()

    comment_mapper = Mock()
    comment_mapper.build_comment_map.return_value = Mock()

    return {
        "scope_mapper": scope_mapper,
        "symbol_mapper": symbol_mapper,
        "symbol_extractor": symbol_extractor,
        "comment_mapper": comment_mapper,
    }


@pytest.fixture
def context_manager_deps(mocks):
    query_mgr = Mock(spec=QueryManager)
    file_manager = Mock(spec=FileManager)
    # Default to returning content for file operations
    file_manager.get_file_content.return_value = b"content"
    file_manager.get_line_count.return_value = 10
    file_manager.get_file_lines.return_value = ["line1", "line2"]
    file_manager.has_file.return_value = True

    with (
        patch(
            "codestory.core.semantic_analysis.annotation.context_manager.ScopeMapper",
            return_value=mocks["scope_mapper"],
        ),
        patch(
            "codestory.core.semantic_analysis.annotation.context_manager.SymbolMapper",
            return_value=mocks["symbol_mapper"],
        ),
        patch(
            "codestory.core.semantic_analysis.annotation.context_manager.SymbolExtractor",
            return_value=mocks["symbol_extractor"],
        ),
        patch(
            "codestory.core.semantic_analysis.annotation.context_manager.CommentMapper",
            return_value=mocks["comment_mapper"],
        ),
        patch(
            "codestory.core.semantic_analysis.annotation.context_manager.QueryManager.get_instance",
            return_value=query_mgr,
        ),
        patch(
            "codestory.core.semantic_analysis.annotation.context_manager.FileParser.parse_file",
            autospec=True,
        ) as parse_file_patch,
    ):
        # include the patched instances for tests
        mocks.update(
            {
                "query_manager": query_mgr,
                "file_parser_parse": parse_file_patch,
                "file_manager": file_manager,
            }
        )
        yield mocks


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


def test_simplify_overlapping_ranges(context_manager_deps):
    # Test the builder's simplify method directly
    builder = ContextManagerBuilder([], context_manager_deps["file_manager"], False)

    ranges = [(1, 5), (3, 7), (10, 12)]
    simplified = builder._simplify_overlapping_ranges(ranges)

    # (1, 5) and (3, 7) overlap -> (1, 7)
    # (10, 12) is separate
    assert simplified == [(1, 7), (10, 12)]

    # Touching ranges
    ranges_touching = [(1, 5), (6, 10)]
    simplified_touching = builder._simplify_overlapping_ranges(ranges_touching)
    # (1, 5) ends at 5. (6, 10) starts at 6. 5 >= 6-1 (5 >= 5) -> True. Merge.
    assert simplified_touching == [(1, 10)]


def test_build_context_success(context_manager_deps):
    chunk = create_chunk()

    # Setup mocks for successful build - FileManager returns content
    context_manager_deps["file_manager"].get_file_content.return_value = b"content"

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

    cm = ContextManagerBuilder(
        [chunk], context_manager_deps["file_manager"], False
    ).build()

    assert cm.has_context(b"file.txt", "base")
    assert cm.has_context(b"file.txt", "patched")

    ctx = cm.get_context(b"file.txt", "base")
    assert isinstance(ctx, AnalysisContext)
    assert ctx.file_path == b"file.txt"
    assert ctx.commit_hash == "base"


def test_build_context_syntax_error(context_manager_deps):
    chunk = create_chunk()

    # Setup mocks - FileManager returns content
    context_manager_deps["file_manager"].get_file_content.return_value = b"content"

    # Create successful parse for base, and failed parse (syntax error) for patched
    base_parse = Mock()
    base_parse.root_node.has_error = False
    base_parse.root_node.children = []
    base_parse.detected_language = "python"
    base_parse.content_bytes = b"content"
    base_parse.line_ranges = []

    patched_parse = Mock()
    patched_parse.root_node.has_error = True
    patched_parse.detected_language = "python"
    patched_parse.content_bytes = b"content"
    patched_parse.line_ranges = []

    # Make QueryManager return a harmless config
    cfg = Mock()
    cfg.share_tokens_between_files = False
    context_manager_deps["query_manager"].get_config.return_value = cfg

    # Patch parse to return different results based on the commit_hash
    def side_effect(path, content, ranges):
        # We need to know which commit we are parsing.
        # But parse_file doesn't know.
        # However, _generate_parsed_files calls it in order of self._required_contexts.items().
        # In this test, base usually comes first because of sorted() or insertion order?
        # A safer way is to check the content or just alternate.
        if not hasattr(side_effect, "call_count"):
            side_effect.call_count = 0
        res = base_parse if side_effect.call_count == 0 else patched_parse
        side_effect.call_count += 1
        return res

    context_manager_deps["file_parser_parse"].side_effect = side_effect

    cm = ContextManagerBuilder(
        [chunk],
        context_manager_deps["file_manager"],
        False,
    ).build()

    assert cm.has_context(b"file.txt", "base")
    assert not cm.has_context(b"file.txt", "patched")

    # When fail_on_syntax_errors=True, building should raise SyntaxErrorDetected
    from codestory.core.exceptions import SyntaxErrorDetected

    with pytest.raises(SyntaxErrorDetected):
        ContextManagerBuilder(
            [chunk],
            context_manager_deps["file_manager"],
            True,
        ).build()
