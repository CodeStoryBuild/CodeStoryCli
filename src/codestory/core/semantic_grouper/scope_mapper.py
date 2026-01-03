"""

-----------------------------------------------------------------------------

/*

 * Copyright (C) 2025 CodeStory

 *

 * This program is free software; you can redistribute it and/or modify

 * it under the terms of the GNU General Public License as published by

 * the Free Software Foundation; Version 2.

 *

 * This program is distributed in the hope that it will be useful,

 * but WITHOUT ANY WARRANTY; without even the implied warranty of

 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the

 * GNU General Public License for more details.

 *

 * You should have received a copy of the GNU General Public License

 * along with this program; if not, you can contact us at support@codestory.build

 */

-----------------------------------------------------------------------------

"""

from dataclasses import dataclass

from tree_sitter import Node

from codestory.core.semantic_grouper.query_manager import QueryManager


@dataclass(frozen=True)
class ScopeMap:
    """Maps each line number to scope inside it."""

    scope_lines: dict[int, set[str]]


class ScopeMapper:
    """Handles scope mapping for source files using Tree-sitter queries."""

    def __init__(self, query_manager: QueryManager):
        self.query_manager = query_manager

    def build_scope_map(
        self,
        language_name: str,
        root_node: Node,
        file_name: bytes,
        content_bytes: bytes,
        line_ranges: list[tuple[int, int]],
    ) -> ScopeMap:
        """

        PASS 1: Traverses the AST to build a map of line numbers to their scope.


        Args:

            language_name: The programming language (e.g., "python", "javascript")

            root_node: The root node of the parsed AST

            file_name: Name of the file being processed (for debugging/context)

            content_bytes: The raw bytes of the file content

            line_ranges: list of tuples (start_line, end_line), to filter the tree sitter queries for a file


        Returns:

            ScopeMap containing the mapping of line numbers to scope names

        """

        line_to_scope: dict[int, set[str]] = {}

        # Run scope queries using the query manager

        scope_captures = self.query_manager.run_query(
            language_name,
            root_node,
            query_type="scope",
            line_ranges=line_ranges,
        )

        for _, nodes in scope_captures.items():
            for node in nodes:
                # Extract the first line of the scope for semantic context

                # Slice from node start to end, then find first newline

                node_bytes = content_bytes[node.start_byte : node.end_byte]

                # Find the first newline to get only the first line

                newline_pos = node_bytes.find(b"\n")

                if newline_pos != -1:
                    first_line_bytes = node_bytes[:newline_pos]

                else:
                    first_line_bytes = node_bytes

                # Decode and strip whitespace

                first_line_text = first_line_bytes.decode(
                    "utf8", errors="replace"
                ).strip()

                # Truncate if too long to keep scope names manageable

                if len(first_line_text) > 80:
                    first_line_text = first_line_text[:77] + "..."

                # Create scope name: file:node_id:first_line_content

                scope_name = f"{file_name.decode('utf8', errors='replace')}:{node.id}:{first_line_text}"

                for line_num in range(node.start_point[0], node.end_point[0] + 1):
                    line_to_scope.setdefault(line_num, set()).add(scope_name)

        return ScopeMap(scope_lines=line_to_scope)
