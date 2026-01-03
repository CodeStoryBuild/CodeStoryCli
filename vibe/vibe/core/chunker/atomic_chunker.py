from collections import defaultdict
from .interface import MechanicalChunker
from ..data.chunk import Chunk
from ..data.diff_chunk import DiffChunk
from ..data.composite_diff_chunk import CompositeDiffChunk

class AtomicChunker(MechanicalChunker):
    
    @staticmethod
    def is_whitespace(line: str) -> bool:
        return line.strip() == ""

    def chunk(self, diff_chunks: list[Chunk]) -> list[Chunk]:
        mechanical_chunks = []
        for chunk in diff_chunks:
            if isinstance(chunk, DiffChunk):
                mechanical_chunks.extend(self.group_by_predicate(self.is_whitespace, chunk.split_into_atomic_chunks()))
            else:
                mechanical_chunks.append(chunk)

        return mechanical_chunks
    
    def satisfys_predicate(self, chunk: DiffChunk, line_predicate) -> bool:
        return all((line_predicate(line.content) for line in chunk.parsed_content))
    
    def group_by_predicate(self, line_predicate, chunks: list[DiffChunk]) -> list[Chunk]:
        n = len(chunks)
        i = 0

        grouped = []

        while i < n:
            current_chunk = chunks[i]
            combined_indices = []
            
            while i < n and self.satisfys_predicate(chunks[i], line_predicate):
                combined_indices.append(i)
                i += 1
            
            if combined_indices:
                group_chunk = chunks[combined_indices[0]]
                if len(combined_indices) > 1:
                    group_chunk = CompositeDiffChunk(list(chunks[idx] for idx in combined_indices))
                
                grouped.append((group_chunk, True)) 
            else:
                grouped.append((current_chunk, False))
                i += 1
        
        if len(grouped) == 1:
            return [grouped[0][0]]
        
        links: dict[int, list[Chunk]] = defaultdict(list)

        for i, (group, satisfys) in enumerate(grouped):
            if satisfys:
                if i == 0:
                    links[i + 1].append(group)
                else:
                    links[i - 1].append(group)
            else:
                links[i].append(group)

        final_groups = []
        
        for i in sorted(links.keys()):
            chunk_list = links[i]
            
            if len(chunk_list) > 1:
                final_groups.append(CompositeDiffChunk(chunk_list))
            else:
                final_groups.append(chunk_list[0])
                
        return final_groups