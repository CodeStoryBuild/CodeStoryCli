from dataclasses import dataclass
from tree_sitter import Node
from collections import defaultdict
from typing import Dict

from .query_manager import QueryManager


@dataclass(frozen=True)
class ScopeMap:
    """Maps each line number to its most specific qualified scope name."""
    scope_lines: defaultdict[int, str]


class ScopeMapper:
    """Handles scope mapping for source files using Tree-sitter queries."""
    
    def __init__(self, query_manager: QueryManager):
        self.query_manager = query_manager
    
    def build_scope_map(self, language_name: str, root_node: Node, file_name: str) -> ScopeMap:
        """
        PASS 1: Traverses the AST to build a map of line numbers to their scope.
        
        Args:
            language_name: The programming language (e.g., "python", "javascript")
            root_node: The root node of the parsed AST
            file_name: Name of the file being processed (for debugging/context)
            
        Returns:
            ScopeMap containing the mapping of line numbers to scope names
        """
        def get_default():
            # for now, we mark the "module level" or "default scope" as None
            return None
        
        line_to_scope = defaultdict(get_default)
        
        # Run scope queries using the query manager
        scope_captures = self.query_manager.run_query(language_name, root_node, is_scope_query=True)
        
        # Extract scope nodes from captures
        scope_nodes = []
        for capture_name, nodes in scope_captures.items():
            scope_nodes.extend(nodes)
        
        # Sort scope nodes by their starting line for proper nesting
        sorted_scope_nodes = sorted(scope_nodes, key=lambda node: node.start_point[0])
        
        # Map each line within scope nodes to the scope node's ID
        for scope_node in sorted_scope_nodes:
            for line_num in range(scope_node.start_point[0], scope_node.end_point[0] + 1):
                if line_num not in line_to_scope:
                    line_to_scope[line_num] = scope_node.id
        
        return ScopeMap(scope_lines=line_to_scope)