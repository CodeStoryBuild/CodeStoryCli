from dataclasses import dataclass, field
from tree_sitter import Node
from collections import defaultdict
from typing import Dict, Optional, List, Tuple

from .query_manager import QueryManager

@dataclass
class ScopeNode:
    """Represents a single scope object in the hierarchy."""
    id: str  # The qualified name of the scope (e.g., 'ClassName.methodName')
    start_line: int
    end_line: int
    node: Node = field(repr=False) # The original tree-sitter node
    parent: Optional['ScopeNode'] = field(default=None, init=False, repr=False)
    children: List['ScopeNode'] = field(default_factory=list, init=False)

@dataclass(frozen=True)
class ScopeMap:
    """
    Holds the hierarchical structure (a forest) of scope objects,
    enabling Least Common Ancestor (LCA) lookups.
    """
    top_level_scopes: List[ScopeNode]

    def get_lca_scope_for_range(self, line_range: Tuple[int, int]) -> Optional[ScopeNode]:
        """
        Finds the Least Common Ancestor (LCA) Scope Node that fully
        contains the given line range [start_line, end_line].
        """
        start_line, end_line = line_range

        # 1. Find all scopes that fully contain the line range
        # We only need to check the top-level scopes and their children recursively.
        candidates: List[ScopeNode] = []
        
        def find_containing_scopes(node: ScopeNode):
            if node.start_line <= start_line and node.end_line >= end_line:
                candidates.append(node)
                # Keep searching children, as a deeper scope might also contain the range
                for child in node.children:
                    find_containing_scopes(child)

        for top_scope in self.top_level_scopes:
            find_containing_scopes(top_scope)

        if not candidates:
            # If no scope contains the entire range, return None (global/file scope)
            return None

        # 2. The LCA scope is the deepest/most specific containing scope.
        # This is the one with the *smallest* line range (end_line - start_line).
        # Since we sorted the candidates by range size, the last one is the largest, 
        # so we need to sort to find the smallest range, which is the deepest.
        
        # Sort by range size (end - start + 1) ascending. 
        # The first element is the smallest containing scope (the LCA).
        candidates.sort(key=lambda s: (s.end_line - s.start_line, s.start_line))

        return candidates[0]


class ScopeMapper:
    """Handles scope mapping for source files using Tree-sitter queries."""

    def __init__(self, query_manager: QueryManager):
        self.query_manager = query_manager

    def _get_scope_objects(self, language_name: str, root_node: Node, line_ranges: list[tuple[int, int]]):
        """Helper to run queries and format results into ScopeNode objects."""
        scope_captures = self.query_manager.run_query(
            language_name, root_node, query_type="scope", line_ranges=line_ranges
        )

        scope_objects: List[ScopeNode] = []
        for capture_name, nodes in scope_captures.items():
            for node in nodes:
                scope_id = f"Scope@{node.id}"
                
                start_line = node.start_point[0]
                end_line = node.end_point[0]
                
                scope_objects.append(
                    ScopeNode(
                        id=scope_id,
                        start_line=start_line,
                        end_line=end_line,
                        node=node,
                    )
                )
        return scope_objects

    def build_scope_map(
        self,
        language_name: str,
        root_node: Node,
        file_name: str,
        line_ranges: list[tuple[int, int]],
    ) -> ScopeMap:
        """
        Builds a sparse, hierarchical scope map (forest) using a stack-based 
        approach to determine containment and parent/child relationships.
        """
        
        scope_objects = self._get_scope_objects(language_name, root_node, line_ranges)

        # 1. Sort scope objects for stack processing, note we negatively weight the end line as a "tie breaker" to get bigger scopes
        scope_objects.sort(key=lambda s: (s.start_line, -s.end_line))

        # 2. Hierarchical Construction (Stack-Based)
        
        # The stack holds currently "open" scopes, ordered from shallowest to deepest.
        ancestor_stack: List[ScopeNode] = []
        top_level_scopes: List[ScopeNode] = []

        for current_scope in scope_objects:
            
            # A. Clean up the stack (close scopes)
            # Pop any scope whose end line is before or at the current scope's start line.
            # We use '<' for start_line as a scope must truly contain or start *before* the current one.
            while (
                ancestor_stack and 
                ancestor_stack[-1].end_line < current_scope.start_line
            ):
                ancestor_stack.pop()

            # B. Determine Parent
            if ancestor_stack:
                # The scope at the top of the stack is the immediate parent
                parent_scope = ancestor_stack[-1]
                
                # Sanity check: the parent MUST contain the current scope.
                # If not, it means the scope objects were generated incorrectly 
                # (e.g., overlapping non-contained scopes), so we skip linkage.
                if (
                    parent_scope.start_line <= current_scope.start_line and
                    parent_scope.end_line >= current_scope.end_line
                ):
                    current_scope.parent = parent_scope
                    parent_scope.children.append(current_scope)
                # Else: treat as top-level if it's a parallel or overlapping scope
                else:
                    top_level_scopes.append(current_scope)

            else:
                # Stack is empty, this is a top-level scope
                top_level_scopes.append(current_scope)

            # C. Push to stack
            # Add the current scope to the stack; it is now the deepest "open" scope
            ancestor_stack.append(current_scope)

        return ScopeMap(top_level_scopes=top_level_scopes)