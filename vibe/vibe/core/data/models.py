from dataclasses import dataclass
from typing import List, Optional, Union

@dataclass
class LineNumbered:
    line_number: int


@dataclass
class Addition(LineNumbered):
    """ Represents a single added line of code."""
    content: str

@dataclass
class Removal(LineNumbered):
    """ Represents a single removed line of code."""
    content: str

@dataclass(init=False)
class Move(LineNumbered):
    content: str
    from_line: int
    to_line: int

    def __init__(self, content: str, from_line: int, to_line: int):
        self.content = content
        self.from_line = from_line
        self.to_line = to_line
        # line number will be the to_line in this case
        self.line_number = to_line


@dataclass
class Replacement(LineNumbered):
    """ Represents a line of code replaced with another, on the same line"""
    old_content: str
    new_content: str


def detect_moves(ai_content: List[Union[Addition, Removal]]) -> List[Union[Addition, Removal, Move]]:
    # Map to store removals by content. The value will be a list of line numbers
    # associated with that content, allowing us to pick the lowest.
    removal_map = {}


    out: List[Union[Addition, Removal, Move]] = ai_content.copy()
    
    for i, item in enumerate(out):
        if isinstance(item, Removal):
            removal_map.setdefault(item.content, []).append((item.line_number, i))

    removals = []

    additions = []
    
    for i, item in enumerate(out): 
        if isinstance(item, Addition):
            # If there's a matching removal and it hasn't been used yet
            if item.content in removal_map and removal_map[item.content]:
                from_line, from_idx = removal_map[item.content].pop(0) # Get and remove the lowest line number

                # since a match was found, remove this addition and the associated removal from the list
                removals.append(from_idx)
                removals.append(i)

                # add a new move object
                additions.append(Move(content=item.content, 
                                      from_line=from_line,
                                      to_line=item.line_number))
                
    for rem in sorted(removals, reverse=True):
        del out[rem]

    for add in additions:
        out.append(add)

    return sorted(out, key=lambda x : x.line_number)

def detect_replacements(content: List[Union[Addition, Removal, Move]]) -> List[Union[Addition, Removal, Move, Replacement]]:
    clarified: List[Union[Addition, Removal, Move, Replacement]] = []
    i = 0
    while i < len(content):
        curr = content[i]
        nxt = content[i + 1] if i + 1 < len(content) else None

        if isinstance(curr, Removal) and isinstance(nxt, Addition):
            if curr.line_number == nxt.line_number:
                # Replacement detected
                clarified.append(Replacement(
                    old_content=curr.content,
                    new_content=nxt.content,
                    line_number=curr.line_number
                ))
                i += 2  # skip the next one
                continue

        # Otherwise keep the item as-is
        clarified.append(curr)
        i += 1

    return clarified


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
    content: str
    ai_content: List[Union[Addition, Removal]]
    old_start: int
    old_end: int
    new_start: int
    new_end: int

    def to_patch(self) -> str: 
        """ Convert this chunk into a unified diff string suitable for git apply. This is critical for committing chunks independently or creating patches. """ 
        header = f"--- a/{self.file_path}\n+++ b/{self.file_path}\n"
        old_len = self.old_end - self.old_start + 1
        new_len = self.new_end - self.new_start + 1
        hunk_range = f"@@ -{self.old_start}{',' + str(old_len) if old_len > 0 else ''} +{self.new_start}{',' + str(new_len) if new_len > 0 else ''} @@\n" 
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
            if old_lines:
                new_old_start = min(old_lines)
                new_old_end = max(old_lines)
            else:
                new_old_start = 0 
                new_old_end = 0  # indicate no old lines

            if new_lines:
                new_new_start = min(new_lines)
                new_new_end = max(new_lines)
            else:
                new_new_start = 0
                new_new_end = 0  # indicate no new lines
            
            new_chunks.append(DiffChunk(
                file_path=self.file_path,
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

        if start < 0 or end > len(self.ai_content):
            raise ValueError("Start and End must define a valid range between 0 - chunk length!")
    
        
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
        if old_lines:
            new_old_start = min(old_lines)
            new_old_end = max(old_lines)
        else:
            new_old_start = self.old_start  # or 0
            new_old_end = 0  # indicate no old lines

        if new_lines:
            new_new_start = min(new_lines)
            new_new_end = max(new_lines)
        else:
            new_new_start = self.new_start  # or 0
            new_new_end = 0  # indicate no new lines
        
        return DiffChunk(
            file_path=self.file_path,
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
