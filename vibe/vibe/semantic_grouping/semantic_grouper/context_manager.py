from dataclasses import dataclass
from typing import Dict, List, Optional, Set
from tree_sitter import Node

from vibe.semantic_grouping.file_reader.protocol import FileReader
from vibe.semantic_grouping.file_reader.file_parser import FileParser, ParsedFile
from vibe.core.data.diff_chunk import DiffChunk
from .query_manager import QueryManager
from .scope_mapper import ScopeMapper, ScopeMap
from .symbol_mapper import SymbolMapper, SymbolMap


@dataclass(frozen=True)
class AnalysisContext:
    """Contains the analysis context for a specific file version."""
    file_path: str
    parsed_file: ParsedFile
    scope_map: ScopeMap
    symbol_map: SymbolMap
    is_old_version: bool


class ContextManager:
    """
    Manages analysis context for files mentioned in diff chunks.
    
    Creates scope and symbol maps for old and new versions of files that appear
    in diff chunks, enabling semantic analysis across file changes.
    """
    
    def __init__(
        self, 
        file_parser: FileParser, 
        file_reader: FileReader, 
        query_manager: QueryManager,
        diff_chunks: List[DiffChunk]
    ):
        self.file_parser = file_parser
        self.file_reader = file_reader
        self.query_manager = query_manager
        self.diff_chunks = diff_chunks
        
        # Initialize mappers
        self.scope_mapper = ScopeMapper(query_manager)
        self.symbol_mapper = SymbolMapper(query_manager)
        
        # Context storage: (file_path, is_old_version) -> AnalysisContext
        self._context_cache: Dict[tuple[str, bool], AnalysisContext] = {}
        
        # Determine which file versions need to be analyzed
        self._required_contexts: Set[tuple[str, bool]] = set()
        self._analyze_required_contexts()
        
        # Build all required contexts
        self._build_all_contexts()
    
    def _analyze_required_contexts(self) -> None:
        """
        Analyze diff chunks to determine which file versions need context.
        """
        for chunk in self.diff_chunks:
            if chunk.is_standard_modification:
                # Standard modification: need both old and new versions of the same file
                file_path = chunk.canonical_path()
                self._required_contexts.add((file_path, True))   # old version
                self._required_contexts.add((file_path, False))  # new version
                
            elif chunk.is_file_addition:
                # File addition: only need new version
                file_path = chunk.new_file_path
                self._required_contexts.add((file_path, False))  # new version only
                
            elif chunk.is_file_deletion:
                # File deletion: only need old version
                file_path = chunk.old_file_path
                self._required_contexts.add((file_path, True))   # old version only
                
            elif chunk.is_file_rename:
                # File rename: need old version with old name, new version with new name
                old_path = chunk.old_file_path
                new_path = chunk.new_file_path
                self._required_contexts.add((old_path, True))    # old version with old name
                self._required_contexts.add((new_path, False))   # new version with new name
    
    def _build_all_contexts(self) -> None:
        """
        Build analysis contexts for all required file versions.
        """
        for file_path, is_old_version in self._required_contexts:
            try:
                context = self._build_context(file_path, is_old_version)
                if context:
                    self._context_cache[(file_path, is_old_version)] = context
            except Exception as e:
                # Log error but continue with other files
                print(f"Warning: Failed to build context for {file_path} (old={is_old_version}): {e}")
    
    def _build_context(self, file_path: str, is_old_version: bool) -> Optional[AnalysisContext]:
        """
        Build analysis context for a specific file version.
        
        Args:
            file_path: Path to the file
            is_old_version: True for old version, False for new version
            
        Returns:
            AnalysisContext if successful, None if file cannot be processed
        """
        # Read file content
        content = self.file_reader.read(file_path, old_content=is_old_version)
        if content is None:
            return None
        
        # Parse the file
        parsed_file = self.file_parser.parse_file(file_path, content)
        if parsed_file is None:
            return None
        
        # for now, reject errored files
        if parsed_file.root_node.has_error:
            print(f"WARNING: the {"old version" if is_old_version else "new version"} of {file_path} has syntax errors!")
            return None

        # Build scope map
        scope_map = self.scope_mapper.build_scope_map(
            parsed_file.detected_language, 
            parsed_file.root_node, 
            file_path
        )
        
        # Build symbol map
        symbol_map = self.symbol_mapper.build_symbol_map(
            parsed_file.detected_language,
            parsed_file.root_node,
            scope_map
        )
        
        return AnalysisContext(
            file_path=file_path,
            parsed_file=parsed_file,
            scope_map=scope_map,
            symbol_map=symbol_map,
            is_old_version=is_old_version
        )
    
    def get_context(self, file_path: str, is_old_version: bool) -> Optional[AnalysisContext]:
        """
        Get analysis context for a specific file version.
        
        Args:
            file_path: Path to the file
            is_old_version: True for old version, False for new version
            
        Returns:
            AnalysisContext if available, None if not found or not required
        """
        return self._context_cache.get((file_path, is_old_version))
    
    def get_available_contexts(self) -> List[AnalysisContext]:
        """
        Get all available analysis contexts.
        
        Returns:
            List of all successfully built AnalysisContext objects
        """
        return list(self._context_cache.values())
    
    def has_context(self, file_path: str, is_old_version: bool) -> bool:
        """
        Check if context is available for a specific file version.
        
        Args:
            file_path: Path to the file
            is_old_version: True for old version, False for new version
            
        Returns:
            True if context is available, False otherwise
        """
        return (file_path, is_old_version) in self._context_cache
    
    def get_required_contexts(self) -> Set[tuple[str, bool]]:
        """
        Get the set of required contexts based on diff chunks.
        
        Returns:
            Set of (file_path, is_old_version) tuples that were determined to be needed
        """
        return self._required_contexts.copy()
    
    def get_file_paths(self) -> Set[str]:
        """
        Get all unique file paths that have contexts.
        
        Returns:
            Set of file paths that have at least one context (old or new)
        """
        return {file_path for file_path, _ in self._context_cache.keys()}
