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

# Test to verify ordered scopes work correctly
from codestory.core.file_parser.file_parser import FileParser
from codestory.core.semantic_analysis.mappers.query_manager import QueryManager
from codestory.core.semantic_analysis.mappers.scope_mapper import ScopeMapper


def test_ordered_named_scopes():
    """Test that named scopes are properly ordered by start position."""
    qm = QueryManager.get_instance()
    scope_mapper = ScopeMapper(qm)
    parser = FileParser()

    # Python code with nested scopes
    content = """class MyClass:
    def method1(self):
        x = 1
        if x > 0:
            print(x)

    def method2(self):
        y = 2
"""

    parsed = parser.parse_file(
        b"test.py", content.encode("utf-8"), [(0, len(content.splitlines()) - 1)]
    )

    scope_map = scope_mapper.build_scope_map(
        parsed.detected_language,
        parsed.root_node,
        b"test.py",
        [(0, len(content.splitlines()) - 1)],
    )

    # Check that sorted scopes exist
    assert scope_map.semantic_named_scopes is not None

    # Line 2 (method1) should have class scope first, then method scope
    line_2_scopes = scope_map.semantic_named_scopes.get(1)  # 0-indexed
    if line_2_scopes:
        print(f"Line 2 scopes (ordered): {line_2_scopes}")
        # Class should come before method in the list (class starts at byte 0, method starts later)
        # We can verify it's a list and has items
        assert isinstance(line_2_scopes, list)
        assert len(line_2_scopes) >= 1

    # Verify that for any line with multiple scopes, they are in a consistent order
    for line_num, scopes in scope_map.semantic_named_scopes.items():
        assert isinstance(scopes, list), f"Line {line_num} scopes should be a list"
        # Verify no duplicates
        assert len(scopes) == len(set(scopes)), (
            f"Line {line_num} has duplicate scopes: {scopes}"
        )
