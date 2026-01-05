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

from dataclasses import dataclass

from tree_sitter import Node

from codestory.core.semantic_analysis.mappers.query_manager import QueryManager


@dataclass(frozen=True)
class NamedScope:
    """A named scope with its name and type (e.g., function, class)."""

    name: str
    scope_type: str


@dataclass(frozen=True)
class ScopeMap:
    """Maps each line number to scope inside it."""

    structural_scope_lines: dict[int, set[str]]
    # Ordered list of named scopes per line, sorted by start position (for FQN construction)
    semantic_named_scopes: dict[int, list[NamedScope]]


class ScopeMapper:
    """Handles scope mapping for source files using tree-sitter queries."""

    def __init__(self, query_manager: QueryManager):
        self.query_manager = query_manager

    def build_scope_map(
        self,
        language_name: str,
        root_node: Node,
        file_name: bytes,
        line_ranges: list[tuple[int, int]],
    ) -> ScopeMap:
        """
        PASS 1: Traverses the AST to build a map of line numbers to their scope.

        Args:
            language_name: The programming language (e.g., "python", "javascript")
            root_node: The root node of the parsed AST
            file_name: Name of the file being processed (for debugging/context)
            line_ranges: list of tuples (start_line, end_line), to filter the tree sitter queries for a file

        Returns:
            ScopeMap containing the mapping of line numbers to named and structural scope names
        """
        line_to_structural_scope: dict[int, set[str]] = {}
        # Track named scopes with their start positions and types for ordering
        line_to_named_scope_with_pos: dict[
            int, list[tuple[int, str, str]]
        ] = {}  # (start_byte, name, scope_type)

        # Run named_scope queries using run_typed_scope_matches to get matches with type info
        typed_matches = self.query_manager.run_typed_scope_matches(
            language_name,
            root_node,
            line_ranges=line_ranges,
        )

        # Process named_scope matches for fully-qualified names with types
        for match, scope_type in typed_matches:
            # Get the scope nodes (captured as @named_scope) and name nodes
            name_nodes = match[1].get("named_scope.name", [])
            scope_nodes = match[1].get("named_scope", [])

            if len(name_nodes) != len(scope_nodes):
                raise RuntimeError(
                    f"Mismatch in named scope match: {len(name_nodes)} name nodes vs {len(scope_nodes)} scope nodes",
                    "Language config must ensure each named_scope has a name capture.",
                )

            for name_node, scope_node in zip(name_nodes, scope_nodes, strict=True):
                # Get the FQN name from the name capture if available
                fqn_name = name_node.text.decode("utf8", errors="replace").strip()

                # Truncate if too long to keep scope names manageable
                if len(fqn_name) > 80:
                    fqn_name = fqn_name[:77] + "..."

                for line_num in range(
                    scope_node.start_point[0], scope_node.end_point[0] + 1
                ):
                    line_to_named_scope_with_pos.setdefault(line_num, []).append(
                        (scope_node.start_byte, fqn_name, scope_type)
                    )

        # Manual traversal for structural scopes: any multi-line node (except root)
        root_nodes = self.query_manager.get_root_node_name(language_name)
        file_name_str = file_name.decode("utf8", errors="replace")

        def traverse(node: Node):
            # Check if node intersects with any line range
            node_start = node.start_point[0]
            node_end = node.end_point[0]

            intersects = False
            for r_start, r_end in line_ranges:
                if not (node_end < r_start or node_start > r_end):
                    intersects = True
                    break

            if not intersects:
                return

            # Skip root node and single-line nodes
            # We check both node.parent is None and the explicit root_node_name from config
            is_root = node.type.lower() in root_nodes
            is_multi_line = node_start != node_end

            if not is_root and is_multi_line:
                scope_name = f"{file_name_str}:{node.id}"
                for line_num in range(node_start, node_end + 1):
                    line_to_structural_scope.setdefault(line_num, set()).add(scope_name)
                # Optimization: Stop early if we found a multi-line node
                # because all its children will be grouped by this node's range anyway.
                return

            # Recurse into children
            for child in node.children:
                traverse(child)

        traverse(root_node)

        # Build sorted named scope mapping with NamedScope objects
        line_to_named_scope_sorted: dict[int, list[NamedScope]] = {}
        for line_num, scopes_with_pos in line_to_named_scope_with_pos.items():
            # Sort by start position, then create NamedScope objects
            sorted_scopes = [
                NamedScope(name=name, scope_type=scope_type)
                for _, name, scope_type in sorted(scopes_with_pos, key=lambda x: x[0])
            ]
            line_to_named_scope_sorted[line_num] = sorted_scopes

        return ScopeMap(
            structural_scope_lines=line_to_structural_scope,
            semantic_named_scopes=line_to_named_scope_sorted,
        )
