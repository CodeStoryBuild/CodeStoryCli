from dataclasses import dataclass
from tree_sitter import Node

from .query_manager import QueryManager
from .scope_mapper import ScopeMap


@dataclass(frozen=True)
class SymbolMap:
    """Maps line number to a set of fully-qualified symbols on that line."""

    line_symbols: dict[int, set[str]]


class SymbolMapper:
    """Handles symbol mapping for source files using Tree-sitter queries."""

    def __init__(self, query_manager: QueryManager):
        self.query_manager = query_manager

    def build_symbol_map(
        self,
        language_name: str,
        root_node: Node,
        defined_symbols: set[str],
        line_ranges: list[tuple[int, int]],
    ) -> SymbolMap:
        """
        PASS 2: Builds a map of line numbers to their fully-qualified symbols.

        Args:
            language_name: The programming language (e.g., "python", "javascript")
            root_node: The root node of the parsed AST
            scope_map: The scope map containing line-to-scope mappings
            line_ranges: list of tuples (start_line, end_line), to filter the tree sitter queries for a file

        Returns:
            SymbolMap containing the mapping of line numbers to qualified symbols
        """
        # Run symbol queries using the query manager
        symbol_captures = self.query_manager.run_query(
            language_name,
            root_node,
            query_type="token_general",
            line_ranges=line_ranges,
        )

        line_symbols_mut: dict[int, set[str]] = {}

        # Process each captured symbol
        for match_class, nodes in symbol_captures.items():
            for node in nodes:

                text = node.text.decode("utf8", errors="replace")

                qualified_symbol = QueryManager.create_qualified_symbol(
                    match_class, text
                )

                if qualified_symbol in defined_symbols:
                    start_line = node.start_point[0]
                    end_line = node.start_point[1]

                    for i in range(start_line, end_line + 1):
                        # we can group on this symbol

                        # Add the qualified symbol to the line's symbol set
                        line_symbols_mut.setdefault(start_line, set()).add(qualified_symbol)

        return SymbolMap(line_symbols=line_symbols_mut)
