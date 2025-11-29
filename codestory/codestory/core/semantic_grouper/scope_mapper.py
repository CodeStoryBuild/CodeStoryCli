# -----------------------------------------------------------------------------
# codestory - Dual Licensed Software
# Copyright (c) 2025 Adem Can
#
# This file is part of codestory.
#
# codestory is available under a dual-license:
#   1. AGPLv3 (Affero General Public License v3)
#      - See LICENSE.txt and LICENSE-AGPL.txt
#      - Online: https://www.gnu.org/licenses/agpl-3.0.html
#
#   2. Commercial License
#      - For proprietary or revenue-generating use,
#        including SaaS, embedding in closed-source software,
#        or avoiding AGPL obligations.
#      - See LICENSE.txt and COMMERCIAL-LICENSE.txt
#      - Contact: ademfcan@gmail.com
#
# By using this file, you agree to the terms of one of the two licenses above.
# -----------------------------------------------------------------------------


from dataclasses import dataclass

from tree_sitter import Node

from .query_manager import QueryManager


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
        file_name: str,
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
                scope_name = f"{file_name}:{node.id}"
                for line_num in range(node.start_point[0], node.end_point[0] + 1):
                    line_to_scope.setdefault(line_num, set()).add(scope_name)

        return ScopeMap(scope_lines=line_to_scope)
