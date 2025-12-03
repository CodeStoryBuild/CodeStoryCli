from tree_sitter import Node

from .query_manager import QueryManager


class SymbolExtractor:
    """Handles symbol extraction for source files using Tree-sitter queries."""

    def __init__(self, query_manager: QueryManager):
        self.query_manager = query_manager

    def extract_defined_symbols(
        self,
        language_name: str,
        root_node: Node,
        line_ranges: list[tuple[int, int]],
    ) -> set[str]:
        """
        PASS 2: Builds a map of line numbers to their fully-qualified symbols.

        Args:
            language_name: The programming language (e.g., "python", "javascript")
            root_node: The root node of the parsed AST
            line_ranges: list of tuples (start_line, end_line), to filter the tree sitter queries for a file

        Returns:
            set containing qualified symbols
        """
        # Run symbol queries using the query manager
        defined_symbol_captures = self.query_manager.run_query(
            language_name,
            root_node,
            query_type="token_definition",
            line_ranges=line_ranges,
        )

        symbols = set()

        # Process each captured symbol
        for match_class, nodes in defined_symbol_captures.items():
            for node in nodes:
                text = node.text.decode("utf8", errors="replace")

                qualified_symbol = QueryManager.create_qualified_symbol(
                    match_class, text
                )

                # Add the qualified symbol to the line's symbol set
                symbols.add(qualified_symbol)

        return symbols
