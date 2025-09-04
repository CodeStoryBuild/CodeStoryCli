from dataclasses import dataclass
from typing import List, Optional, Union

@dataclass
class Addition:
    """Represents a single added line of code."""
    content: str
    line_number: int

@dataclass
class Removal:
    """Represents a single removed line of code."""
    content: str
    line_number: int

@dataclass
class DiffChunk:
    """
    Represents a single diff chunk or sub-hunk.

    Responsibilities:
    - Must contain enough information to reconstruct a patch for Git
    - Preserves file path, line numbers, and content
    - Can be serialized into a unified diff format

    Attributes:
        file_path: Path of the file this chunk belongs to
        start_line: Start line number in the original file
        end_line: End line number in the original file
        content: The raw, human-readable lines of code in this chunk (with +/- prefixes)
        ai_content: A structured, AI-legible list of Addition and Removal objects
        old_start: Optional start line in original version (for patch)
        old_end: Optional end line in original version
        new_start: Optional start line in new version
        new_end: Optional end line in new version
    """
    file_path: str
    start_line: int
    end_line: int
    content: str
    ai_content: List[Union[Addition, Removal]]
    old_start: Optional[int] = None
    old_end: Optional[int] = None
    new_start: Optional[int] = None
    new_end: Optional[int] = None

    def to_patch(self) -> str:
        """
        Convert this chunk into a unified diff string suitable for `git apply`.
        This is critical for committing chunks independently or creating patches.
        """
        header = f"--- a/{self.file_path}\n+++ b/{self.file_path}\n"
        hunk_range = f"@@ -{self.old_start},{self.old_end - self.old_start + 1} +{self.new_start},{self.new_end - self.new_start + 1} @@\n"
        return header + hunk_range + self.content

    def split(self, split_indices: List[int]) -> List['DiffChunk']:
        """
        Splits this DiffChunk into multiple, smaller DiffChunks.
        
        Args:
            split_indices: A list of indices into the ai_content list where the
                           splits should occur.
        
        Returns:
            A list of new DiffChunk objects, each representing a valid sub-chunk.
        """
        indices = sorted([0] + split_indices + [len(self.ai_content)])
        new_chunks = []
        
        for i in range(len(indices) - 1):
            start_index = indices[i]
            end_index = indices[i+1]
            
            # Create the ai_content slice for the new chunk
            new_ai_content = self.ai_content[start_index:end_index]
            if not new_ai_content:
                continue

            # Rebuild the raw content and recalculate line numbers for the new chunk
            new_content = ""
            old_lines = []
            new_lines = []
            
            for item in new_ai_content:
                if isinstance(item, Addition):
                    new_content += f"+{item.content}\n"
                    new_lines.append(item.line_number)
                elif isinstance(item, Removal):
                    new_content += f"-{item.content}\n"
                    old_lines.append(item.line_number)

            # Recalculate start and end line numbers for the patch
            new_old_start = min(old_lines) if old_lines else self.old_start
            new_old_end = max(old_lines) if old_lines else self.old_start - 1
            new_new_start = min(new_lines) if new_lines else self.new_start
            new_new_end = max(new_lines) if new_lines else self.new_start - 1
            
            new_chunks.append(DiffChunk(
                file_path=self.file_path,
                start_line=new_new_start,
                end_line=new_new_end,
                content=new_content.strip(),
                ai_content=new_ai_content,
                old_start=new_old_start,
                old_end=new_old_end,
                new_start=new_new_start,
                new_end=new_new_end
            ))

        return new_chunks
    
    def extract(self, start: int, end : int) -> 'DiffChunk':
        """
        Extracts a smaller DiffChunk from this DiffChunk
        
        Args:
            start: (Inclusive) The start of the subchunk
            end: (Exclusive) The end of the subchunk
                           splits should occur.
        
        Returns:
            A new DiffChunk object, representing a valid sub-chunk.
        """
    
        
        # Create the ai_content slice for the new chunk
        new_ai_content = self.ai_content[start:end]
        if not new_ai_content:
            return None

        # Rebuild the raw content and recalculate line numbers for the new chunk
        new_content = ""
        old_lines = []
        new_lines = []
        
        for item in new_ai_content:
            if isinstance(item, Addition):
                new_content += f"+{item.content}\n"
                new_lines.append(item.line_number)
            elif isinstance(item, Removal):
                new_content += f"-{item.content}\n"
                old_lines.append(item.line_number)

        # Recalculate start and end line numbers for the patch
        new_old_start = min(old_lines) if old_lines else self.old_start
        new_old_end = max(old_lines) if old_lines else self.old_start - 1
        new_new_start = min(new_lines) if new_lines else self.new_start
        new_new_end = max(new_lines) if new_lines else self.new_start - 1
        
        return DiffChunk(
            file_path=self.file_path,
            start_line=new_new_start,
            end_line=new_new_end,
            content=new_content.strip(),
            ai_content=new_ai_content,
            old_start=new_old_start,
            old_end=new_old_end,
            new_start=new_new_start,
            new_end=new_new_end
        )


@dataclass
class ChunkGroup:
    """
    A collection of DiffChunks that are committed together.
    """
    chunks: List[DiffChunk]
    group_id: str
    description: Optional[str] = None
    
    def to_patch(self) -> str:
        """Concatenates the patches of all chunks in the group."""
        return "\n".join(chunk.to_patch() for chunk in self.chunks)

@dataclass
class CommitResult:
    """
    Result of a commit operation.
    """
    commit_hash: str
    group: ChunkGroup
