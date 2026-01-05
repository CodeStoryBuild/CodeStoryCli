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

from codestory.core.diff.data.line_changes import Addition, Removal
from codestory.core.diff.data.standard_diff_chunk import StandardDiffChunk
from codestory.core.semantic_analysis.grouping.semantic_grouper import SemanticGrouper
from codestory.core.semantic_analysis.mappers.scope_mapper import NamedScope

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def create_chunk(
    old_path=b"file.txt",
    new_path=b"file.txt",
    old_start=1,
    old_len=0,
    new_start=1,
    new_len=0,
):
    """Helper to create a StandardDiffChunk with minimal necessary data."""
    parsed_content = []
    # Add dummy content to satisfy has_content and length calculations
    for i in range(old_len):
        parsed_content.append(Removal(old_start + i, new_start, b"old"))
    for i in range(new_len):
        parsed_content.append(Addition(old_start, new_start + i, b"new"))

    return StandardDiffChunk(
        base_hash="base",
        new_hash="new",
        old_file_path=old_path,
        new_file_path=new_path,
        parsed_content=parsed_content,
        old_start=old_start,
    )


@pytest.fixture
def context_manager():
    cm = Mock()
    contexts = {}

    # Helper to configure context for a specific file/version
    def configure_context(path, is_old, symbols=None, scopes=None):
        ctx = Mock()
        ctx.detected_language = "python"
        ctx.symbol_map.modified_line_symbols = symbols or {}
        ctx.symbol_map.extern_line_symbols = {}
        ctx.scope_map.structural_scope_lines = scopes or {}
        ctx.comment_map.pure_comment_lines = set()
        # Build sorted version from scopes dict
        ctx.scope_map.semantic_named_scopes = {
            line: [NamedScope(name=s, scope_type="class") for s in scope_set]
            for line, scope_set in (scopes or {}).items()
        }

        # Map boolean is_old to hash strings used in tests
        h = "base" if is_old else "new"
        contexts[(path, h)] = ctx
        return ctx

    def get_ctx(p, h):
        return contexts.get((p, h))

    def has_ctx(p, h):
        return (p, h) in contexts

    cm.configure_context = configure_context
    cm.get_context.side_effect = get_ctx
    cm.has_context.side_effect = has_ctx

    return cm


@pytest.fixture
def grouper(context_manager):
    return SemanticGrouper(context_manager=context_manager)


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


def test_group_symbol_overlap(grouper, context_manager):
    """Test grouping chunks that share a symbol."""
    # Chunk 1: lines 1-2, symbol "Foo"
    c1 = create_chunk(new_len=2, new_start=1)
    # Chunk 2: lines 10-11, symbol "Foo"
    c2 = create_chunk(new_len=2, new_start=10)

    # Configure context
    # Both in new version of file.txt
    context_manager.configure_context(
        b"file.txt", False, symbols={0: {"Foo"}, 1: {"Foo"}, 9: {"Foo"}, 10: {"Foo"}}
    )
    # Also need old context for standard modification check
    context_manager.configure_context(b"file.txt", True)

    groups = grouper.group([c1, c2])

    assert len(groups) == 1
    assert len(groups[0].get_atomic_chunks()) == 2
    assert c1 in groups[0].get_atomic_chunks()
    assert c2 in groups[0].get_atomic_chunks()


def test_group_scope_overlap(grouper, context_manager):
    """Test grouping chunks that share a scope."""
    c1 = create_chunk(new_len=1, new_start=5)
    c2 = create_chunk(new_len=1, new_start=20)

    context_manager.configure_context(
        b"file.txt", False, scopes={4: {"ClassA"}, 19: {"ClassA"}}
    )
    context_manager.configure_context(b"file.txt", True)

    groups = grouper.group([c1, c2])

    assert len(groups) == 1
    assert len(groups[0].get_atomic_chunks()) == 2


def test_group_transitive(grouper, context_manager):
    """Test transitive grouping: A-B (sym1), B-C (sym2) -> A-B-C."""
    c1 = create_chunk(new_len=1, new_start=1)  # sym1
    c2 = create_chunk(new_len=1, new_start=10)  # sym1, sym2
    c3 = create_chunk(new_len=1, new_start=20)  # sym2

    context_manager.configure_context(
        b"file.txt", False, symbols={0: {"sym1"}, 9: {"sym1", "sym2"}, 19: {"sym2"}}
    )
    context_manager.configure_context(b"file.txt", True)

    groups = grouper.group([c1, c2, c3])

    assert len(groups) == 1
    assert len(groups[0].get_atomic_chunks()) == 3


def test_group_disjoint(grouper, context_manager):
    """Test that disjoint chunks remain separate."""
    c1 = create_chunk(new_len=1, new_start=1)  # sym1
    c2 = create_chunk(new_len=1, new_start=10)  # sym2

    context_manager.configure_context(
        b"file.txt", False, symbols={0: {"sym1"}, 9: {"sym2"}}
    )
    context_manager.configure_context(b"file.txt", True)

    groups = grouper.group([c1, c2])

    assert len(groups) == 2


def test_fallback_missing_context(grouper, context_manager):
    """Test that chunks with missing context go to fallback group."""
    c1 = create_chunk(new_len=1, new_start=1)  # Has context
    c2 = create_chunk(new_len=1, new_start=10)  # No context

    # Configure context only for c1's range (and file existence)
    # But c2 will fail _has_analysis_context if we don't configure it?
    # Actually _has_analysis_context checks if context EXISTS for the file/version.
    # If it exists, it proceeds to get signature.
    # If get_signature returns empty, it's still "analyzable" but has no symbols.

    # To trigger fallback, we need _has_analysis_context to return False.
    # This happens if context_manager.has_context returns False.

    # Let's say c1 is in file1.txt (has context) and c2 is in file2.txt (no context)
    c1 = create_chunk(old_path=b"f1.txt", new_path=b"f1.txt", new_len=1)
    c2 = create_chunk(old_path=b"f2.txt", new_path=b"f2.txt", new_len=1)

    context_manager.configure_context(b"f1.txt", True)
    context_manager.configure_context(b"f1.txt", False, symbols={0: {"s1"}})

    # Do NOT configure f2.txt

    groups = grouper.group([c1, c2])

    # Expect:
    # Group 1: c1 (analyzable)
    # Group 2: c2 (fallback)
    assert len(groups) == 2
    # Fallback group is always last? Implementation says:
    # "List of semantic groups, with fallback group last if it exists"

    assert groups[0].get_atomic_chunks()[0] == c1
    assert groups[1].get_atomic_chunks()[0] == c2


def test_chunk_types(grouper, context_manager):
    """Test different chunk types (add, del, rename)."""
    # Addition
    c_add = create_chunk(old_path=None, new_path=b"new.txt", new_len=1)
    # Deletion
    c_del = create_chunk(old_path=b"old.txt", new_path=None, old_len=1)

    # Configure contexts
    context_manager.configure_context(b"new.txt", False, symbols={0: {"shared"}})
    context_manager.configure_context(b"old.txt", True, symbols={0: {"shared"}})

    groups = grouper.group([c_add, c_del])

    # Should group because they share "shared" symbol
    assert len(groups) == 1
    assert len(groups[0].get_atomic_chunks()) == 2
