from dataclasses import dataclass
from typing import List, Set, Dict, Optional, Tuple
from collections import defaultdict

from vibe.core.data.chunk import Chunk
from vibe.core.data.diff_chunk import DiffChunk
from vibe.core.data.composite_diff_chunk import CompositeDiffChunk
from vibe.semantic_grouping.file_reader.protocol import FileReader
from vibe.semantic_grouping.file_reader.file_parser import FileParser
from .context_manager import ContextManager, AnalysisContext
from .query_manager import QueryManager
from .union_find import UnionFind
import logging


@dataclass(frozen=True)
class ChunkSignature:
    """Represents the semantic signature of a chunk."""
    chunk_id: int
    symbols: Set[str]
    has_analysis_context: bool
    scope: Optional[str] = None



class SemanticGrouper:
    """
    Groups chunks semantically based on overlapping symbol signatures.
    
    The grouper flattens composite chunks into individual DiffChunks, generates
    semantic signatures for each chunk, and groups chunks with overlapping signatures
    using a union-find algorithm. Chunks that cannot be analyzed are placed in a
    fallback group for safety.
    """
    
    def __init__(
        self, 
        file_parser: FileParser,
        file_reader: FileReader,
        query_manager: QueryManager
    ):
        self.file_parser = file_parser
        self.file_reader = file_reader
        self.query_manager = query_manager
    
    def group_chunks(self, chunks: List[Chunk]) -> List[CompositeDiffChunk]:
        """
        Group chunks semantically based on overlapping symbol signatures.
        
        Args:
            chunks: List of chunks to group semantically
            
        Returns:
            List of semantic groups, with fallback group last if it exists
            
        Raises:
            ValueError: If chunks list is empty
        """
        if not chunks:
            return []
        
        # Step 1: Flatten chunks into DiffChunks
        diff_chunks = self._flatten_chunks(chunks)
        
        if not diff_chunks:
            # All chunks were empty, return fallback group
            return [CompositeDiffChunk(chunks=chunks)]
        
        # Step 2: Build analysis contexts using ContextManager
        try:
            context_manager = ContextManager(
                self.file_parser,
                self.file_reader,
                self.query_manager,
                diff_chunks
            )
        except Exception as e:
            # If context building fails completely, put everything in fallback
            logging.warning(f"Context building failed, using fallback group: {e}")
            return [CompositeDiffChunk(chunks=chunks)]
        
        # Step 3: Generate signatures for each chunk
        chunk_signatures = self._generate_chunk_signatures(chunks, context_manager)
        
        # Step 4: Separate chunks that can be analyzed from those that cannot
        analyzable_chunks = []
        fallback_chunks = []
        
        for signature in chunk_signatures:
            if signature.has_analysis_context:
                analyzable_chunks.append(signature)
            else:
                # Find the original chunk for this signature
                original_chunk = chunks[signature.chunk_id]
                fallback_chunks.append(original_chunk)
        
        # Step 5: Group analyzable chunks using Union-Find based on overlapping signatures
        semantic_groups = []
        if analyzable_chunks:
            grouped_chunks = self._group_by_overlapping_signatures(analyzable_chunks, chunks)
            semantic_groups.extend(grouped_chunks)
        
        # Step 6: Add fallback group if any chunks couldn't be analyzed
        if fallback_chunks:
            fallback_group = CompositeDiffChunk(
                chunks=fallback_chunks,
            )
            semantic_groups.append(fallback_group)
        
        return semantic_groups
    
    def _flatten_chunks(self, chunks: List[Chunk]) -> List[DiffChunk]:
        """
        Flatten all chunks into a list of DiffChunks.
        
        Args:
            chunks: List of chunks (may include composite chunks)
            
        Returns:
            Flattened list of DiffChunks
        """
        diff_chunks = []
        for chunk in chunks:
            diff_chunks.extend(chunk.get_chunks())
        return diff_chunks
    
    def _generate_chunk_signatures(
        self, 
        original_chunks: List[Chunk], 
        context_manager: ContextManager  # No longer need diff_chunks here
    ) -> List[ChunkSignature]:
        """
        Generate semantic signatures for each original chunk.
        """
        chunk_signatures = []
        
        for chunk_id, chunk in enumerate(original_chunks):
            # Get all DiffChunks that belong to this original chunk
            chunk_diff_chunks = chunk.get_chunks()
            
            # Generate signature for this chunk, which might fail (return None)
            signature_result = self._generate_signature_for_chunk(chunk_diff_chunks, context_manager)
            
            if signature_result is None:
                # Analysis failed for this chunk
                chunk_signature = ChunkSignature(
                    chunk_id=chunk_id,
                    symbols=set(),
                    has_analysis_context=False,
                    scope=None
                )
            else:
                # Analysis succeeded, unpack symbols and scope
                symbols, scope = signature_result
                chunk_signature = ChunkSignature(
                    chunk_id=chunk_id,
                    symbols=symbols,
                    has_analysis_context=True,
                    scope=scope
                )
            chunk_signatures.append(chunk_signature)
        
        return chunk_signatures

    def _generate_signature_for_chunk(
        self, 
        diff_chunks: List[DiffChunk], 
        context_manager: ContextManager
    ) -> Optional[tuple[Set[str], Optional[str]]]:  # Return type is now Optional[tuple[Set[str], Optional[str]]]
        """
        Generate a semantic signature for a single chunk.
        Returns tuple of (symbols, scope) if analysis succeeds, None if analysis fails.
        Scope is determined by the LCA scope of the first diff chunk that has a scope.
        """
        if not diff_chunks:
            return (set(), None)  # An empty chunk has a valid, empty signature with no scope
        
        total_signature = set()
        chunk_scope = None
        
        for diff_chunk in diff_chunks:
            try:
                if not self._has_analysis_context(diff_chunk, context_manager):
                    # If any diff chunk lacks context, the entire chunk fails analysis
                    return None  # Signal failure explicitly
                chunk_signature, diff_chunk_scope = self._get_signature_for_diff_chunk(diff_chunk, context_manager)
                total_signature.update(chunk_signature)
                
                # Use the first non-None scope we encounter as the chunk scope
                if chunk_scope is None and diff_chunk_scope is not None:
                    chunk_scope = diff_chunk_scope
                    
            except Exception as e:
                logging.warning(f"Signature generation failed for diff chunk {diff_chunk.canonical_path()}: {e}")
                return None  # Signal failure explicitly
        
        return (total_signature, chunk_scope)
    
    def _has_analysis_context(self, diff_chunk: DiffChunk, context_manager: ContextManager) -> bool:
        """
        Check if we have the necessary analysis context for a DiffChunk.
        
        Args:
            diff_chunk: The DiffChunk to check
            context_manager: ContextManager with analysis contexts
            
        Returns:
            True if we have context, False otherwise
        """
        if diff_chunk.is_standard_modification:
            # Need both old and new contexts
            file_path = diff_chunk.canonical_path()
            return (context_manager.has_context(file_path, True) and 
                    context_manager.has_context(file_path, False))
        
        elif diff_chunk.is_file_addition:
            # Need new context only
            return context_manager.has_context(diff_chunk.new_file_path, False)
        
        elif diff_chunk.is_file_deletion:
            # Need old context only
            return context_manager.has_context(diff_chunk.old_file_path, True)
        
        elif diff_chunk.is_file_rename:
            # Need both old and new contexts with respective paths
            return (context_manager.has_context(diff_chunk.old_file_path, True) and
                    context_manager.has_context(diff_chunk.new_file_path, False))
        
        return False
    
    def _get_signature_for_diff_chunk(
        self, 
        diff_chunk: DiffChunk, 
        context_manager: ContextManager
    ) -> tuple[Set[str], Optional[str]]:
        """
        Generate signature and scope information for a single DiffChunk based on affected line ranges.
        
        Args:
            diff_chunk: The DiffChunk to analyze
            context_manager: ContextManager with analysis contexts
            
        Returns:
            Tuple of (symbols, scope) in the affected line ranges.
            Scope is determined by the LCA scope of the chunk's line ranges.
        """
        signature = set()
        chunk_scope = None
        
        if diff_chunk.is_standard_modification:
            # For modifications, analyze both old and new line ranges
            file_path = diff_chunk.canonical_path()
            
            # Old version signature
            old_context = context_manager.get_context(file_path, True)
            if old_context and diff_chunk.old_start is not None:
                old_end = diff_chunk.old_start + diff_chunk.old_len() - 1
                old_signature, old_scope = self._get_signature_for_line_range(
                    diff_chunk.old_start, old_end, old_context
                )
                signature.update(old_signature)
                if chunk_scope is None and old_scope:
                    chunk_scope = old_scope
            
            # New version signature
            new_context = context_manager.get_context(file_path, False)
            if new_context and diff_chunk.new_start is not None:
                new_end = diff_chunk.new_start + diff_chunk.new_len() - 1
                new_signature, new_scope = self._get_signature_for_line_range(
                    diff_chunk.new_start, new_end, new_context
                )
                signature.update(new_signature)
                if chunk_scope is None and new_scope:
                    chunk_scope = new_scope
        
        elif diff_chunk.is_file_addition:
            # For additions, analyze new version only
            new_context = context_manager.get_context(diff_chunk.new_file_path, False)
            if new_context and diff_chunk.new_start is not None:
                new_end = diff_chunk.new_start + diff_chunk.new_len() - 1
                signature, chunk_scope = self._get_signature_for_line_range(
                    diff_chunk.new_start, new_end, new_context
                )
        
        elif diff_chunk.is_file_deletion:
            # For deletions, analyze old version only
            old_context = context_manager.get_context(diff_chunk.old_file_path, True)
            if old_context and diff_chunk.old_start is not None:
                old_end = diff_chunk.old_start + diff_chunk.old_len() - 1
                signature, chunk_scope = self._get_signature_for_line_range(
                    diff_chunk.old_start, old_end, old_context
                )
        
        elif diff_chunk.is_file_rename:
            # For renames, analyze both versions with their respective paths
            old_context = context_manager.get_context(diff_chunk.old_file_path, True)
            new_context = context_manager.get_context(diff_chunk.new_file_path, False)
            
            if old_context and diff_chunk.old_start is not None:
                old_end = diff_chunk.old_start + diff_chunk.old_len() - 1
                old_signature, old_scope = self._get_signature_for_line_range(
                    diff_chunk.old_start, old_end, old_context
                )
                signature.update(old_signature)
                if chunk_scope is None and old_scope:
                    chunk_scope = old_scope
            
            if new_context and diff_chunk.new_start is not None:
                new_end = diff_chunk.new_start + diff_chunk.new_len() - 1
                new_signature, new_scope = self._get_signature_for_line_range(
                    diff_chunk.new_start, new_end, new_context
                )
                signature.update(new_signature)
                if chunk_scope is None and new_scope:
                    chunk_scope = new_scope
        
        return (signature, chunk_scope)
    
    def _get_signature_for_line_range(
        self, 
        start_line: int, 
        end_line: int, 
        context: AnalysisContext
    ) -> tuple[Set[str], Optional[str]]:
        """
        Get signature and scope information for a specific line range using the analysis context.
        
        Args:
            start_line: Starting line number (1-indexed)
            end_line: Ending line number (1-indexed, inclusive)
            context: AnalysisContext containing symbol map and scope map
            
        Returns:
            Tuple of (symbols, scope) for the specified line range.
            Scope is the LCA scope, simplified to the scope of the first line.
        """
        symbols = set()
        
        if start_line < 1 or end_line < start_line:
            # Invalid line range
            raise ValueError("Invalid line range!")
        
        # Convert from 1-indexed chunks to 0-indexed scope/symbol maps
        # Get scope from the first line (LCA scope)
        lca_scope = context.scope_map.scope_lines.get(start_line - 1)

        print(f"{context.scope_map=}")
        print(f"{context.symbol_map=}")
        
        # Collect symbols from all lines in the range
        for line in range(start_line, end_line + 1):
            # Convert 1-indexed line to 0-indexed for map access
            zero_indexed_line = line - 1
            line_symbols = context.symbol_map.line_symbols.get(zero_indexed_line, set())
            symbols.update(line_symbols)
        
        return (symbols, lca_scope)
    
    def _group_by_overlapping_signatures(
        self, 
        chunk_signatures: List[ChunkSignature], 
        original_chunks: List[Chunk]
    ) -> List[CompositeDiffChunk]:
        """
        Group chunks with overlapping signatures using an efficient
        inverted index and Union-Find algorithm.
        Also groups chunks that share the same scope (if scope is not None).
        """
        if not chunk_signatures:
            return []
        
        print(f"{chunk_signatures=}")
        
        chunk_ids = [sig.chunk_id for sig in chunk_signatures]
        if not chunk_ids:
            return []

        uf = UnionFind(chunk_ids)
        
        # Step 1: Create an inverted index from symbol -> list of chunk_ids
        symbol_to_chunks: Dict[str, List[int]] = defaultdict(list)
        for sig in chunk_signatures:
            # Only consider chunks with symbols for grouping
            if sig.symbols:
                for symbol in sig.symbols:
                    symbol_to_chunks[symbol].append(sig.chunk_id)
        
        # Step 2: Union chunks that share common symbols
        for symbol, ids in symbol_to_chunks.items():
            if len(ids) > 1:
                first_chunk_id = ids[0]
                for i in range(1, len(ids)):
                    uf.union(first_chunk_id, ids[i])
        
        # Step 3: Additional grouping by scope (if scope is not None)
        scope_to_chunks: Dict[str, List[int]] = defaultdict(list)
        for sig in chunk_signatures:
            if sig.scope is not None:  # Only group chunks that have a scope
                scope_to_chunks[sig.scope].append(sig.chunk_id)
        
        # Step 4: Union chunks that share the same scope
        for scope, ids in scope_to_chunks.items():
            if len(ids) > 1:
                first_chunk_id = ids[0]
                for i in range(1, len(ids)):
                    uf.union(first_chunk_id, ids[i])
        
        # Step 5: Group chunks by their root in the Union-Find structure
        groups: Dict[int, List[Chunk]] = defaultdict(list)
        for signature in chunk_signatures:
            root = uf.find(signature.chunk_id)
            original_chunk = original_chunks[signature.chunk_id]
            groups[root].append(original_chunk)
        
        # Convert to SemanticGroup objects
        return [
            CompositeDiffChunk(chunks=group_chunks)
            for group_chunks in groups.values()
        ]