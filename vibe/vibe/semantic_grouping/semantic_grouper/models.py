from dataclasses import dataclass, field
from typing import Optional

from tree_sitter import Node

from vibe.core.data.chunk import Chunk


@dataclass
class Scope:
    """Represents a structural scope like a function or class."""
    id: str
    type: str
    name: str | None
    start_line: int
    end_line: int
    parent: Optional['Scope'] = None
    children: list['Scope'] = field(default_factory=list)

@dataclass
class Symbol:
    """Represents a defined symbol."""
    name: str
    type: str
    definition_scope_id: str

@dataclass
class AnalysedHunk:
    """An internal representation of a single, continuous hunk range."""
    parent_chunk: Chunk  # Reference to the original Chunk
    new_start: int
    new_end: int

    # Fields to be populated by semantic analysis
    structural_scope_id: str = ""
    used_definition_scope_ids: set[str] = field(default_factory=set)

@dataclass
class AnalysisContext:
    """Holds all necessary analysis artifacts for a single file."""
    # 'Before' state artifacts
    before_ast: Node | None = None
    before_scope_tree: Scope | None = None
    before_symbol_table: dict[str, Symbol] = field(default_factory=dict)
    before_all_scopes: dict[str, Scope] = field(default_factory=dict)
    
    # 'After' state artifacts
    after_ast: Node | None = None
    after_scope_tree: Scope | None = None
    after_symbol_table: dict[str, Symbol] = field(default_factory=dict)
    after_all_scopes: dict[str, Scope] = field(default_factory=dict)
