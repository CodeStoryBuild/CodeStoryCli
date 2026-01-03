from dataclasses import dataclass
from tree_sitter import Node
from typing import Dict, Set

from .query_manager import QueryManager
from .scope_mapper import ScopeMap


@dataclass(frozen=True)
class SymbolMap:
    """Maps line number to a set of fully-qualified symbols on that line."""
    line_symbols: Dict[int, Set[str]]


class SymbolMapper:
    """Handles symbol mapping for source files using Tree-sitter queries."""
    
    def __init__(self, query_manager: QueryManager):
        self.query_manager = query_manager
    
    def build_symbol_map(self, language_name: str, root_node: Node, scope_map: ScopeMap) -> SymbolMap:
        """
        PASS 2: Builds a map of line numbers to their fully-qualified symbols.
        
        Args:
            language_name: The programming language (e.g., "python", "javascript")
            root_node: The root node of the parsed AST
            scope_map: The scope map containing line-to-scope mappings
            
        Returns:
            SymbolMap containing the mapping of line numbers to qualified symbols
        """
        # Run symbol queries using the query manager
        symbol_captures = self.query_manager.run_query(language_name, root_node, is_scope_query=False)
        
        line_symbols_mut: Dict[int, Set[str]] = {}
        
        # Process each captured symbol
        for match_class, nodes in symbol_captures.items():
            for node in nodes:
                text = node.text.decode("utf8", errors="replace")
                start_line = node.start_point[0]
                
                # Get scope name for this line
                scope_name = scope_map.scope_lines.get(start_line)
                
                # TODO work on making signature creation more customizable
                # for example, should we require matching scopes for shared symbols, 
                # probably not, but maybe in certain cases
                # qualified_symbol = f"{scope_name}:{match_class}:{text}"
                qualified_symbol = f"{match_class}:{text}"
                
                # Add the qualified symbol to the line's symbol set
                line_symbols_mut.setdefault(start_line, set()).add(qualified_symbol)
        
        return SymbolMap(line_symbols=line_symbols_mut)