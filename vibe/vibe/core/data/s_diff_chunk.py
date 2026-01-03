from vibe.core.data.diff_chunk import DiffChunk
from vibe.core.data.models import Addition, Removal, Move, Replacement
from dataclasses import dataclass
from typing import List, Optional, Union
import json


@dataclass
class StandardDiffChunk(DiffChunk):
    """
    Represents a single diff chunk or sub-hunk.

    Responsibilities:
    - Must contain enough information to reconstruct a patch for Git
    - Preserves file path, line numbers, and content
    - Can be serialized into a unified diff format
    - GUARANTEES that ai_content represents a contiguous block of changes

    Attributes:
        file_path: Path of the file this chunk belongs to
        start_line: Start line number in the original file
        end_line: End line number in the original file
        content: The raw, human-readable lines of code in this chunk (with +/- prefixes)
        ai_content: A structured, AI-legible list of Addition and Removal objects (MUST be contiguous)
        old_start: Optional start line in original version (for patch)
        new_start: Optional start line in new version
    """
    file_path: str
    content: str
    ai_content: List[Union[Addition, Removal]]
    old_start: int
    new_start: int

    def __post_init__(self):
        """Validate that this chunk represents a contiguous block of changes."""
        self._validate_contiguity()

    def _validate_contiguity(self):
        """
        Validates that ai_content represents a contiguous block of changes.
        
        Rules for git patch contiguity:
        1. All removals must be on consecutive line numbers starting from old_start
        2. All additions must be on consecutive line numbers starting from new_start
        3. old_start and new_start can be different (this is normal for git patches)
        
        Raises:
            ValueError: If the chunk is not contiguous within its removal/addition blocks
        """
        if not self.ai_content:
            return
            
        # Separate removals and additions
        removals = [item for item in self.ai_content if isinstance(item, Removal)]
        additions = [item for item in self.ai_content if isinstance(item, Addition)]
        
        # Check that removals are contiguous starting from old_start
        if removals:
            removal_lines = sorted([r.line_number for r in removals])
            expected_line = self.old_start
            for actual_line in removal_lines:
                if actual_line != expected_line:
                    raise ValueError(f"Non-contiguous removals: expected line {expected_line}, got {actual_line}")
                expected_line += 1
        
        # Check that additions are contiguous starting from new_start  
        if additions:
            addition_lines = sorted([a.line_number for a in additions])
            expected_line = self.new_start
            for actual_line in addition_lines:
                if actual_line != expected_line:
                    raise ValueError(f"Non-contiguous additions: expected line {expected_line}, got {actual_line}")
                expected_line += 1

    # override
    def to_patch(self) -> str:
        """
        Generates a valid git patch hunk string from the chunk's data.
        This is the inverse of the parsing logic.
        """
        # Separate additions and removals to get accurate counts
        removals = [item for item in self.ai_content if isinstance(item, Removal)]
        additions = [item for item in self.ai_content if isinstance(item, Addition)]
        
        old_count = len(removals)
        new_count = len(additions)

        # The header is the most important part
        header = f"@@ -{self.old_start},{old_count} +{self.new_start},{new_count} @@\n"

        patch_content = self.content
        
        # always ensure trailing newlines
        if not patch_content.endswith("\n"):
            patch_content += "\n"
        
        # If this chunk represents a rename, emit rename metadata            
        f_header = f"--- a/{self.file_path}\n+++ b/{self.file_path}\n"

        return f_header + header + patch_content

    def split(self, split_indices: List[int]) -> List['DiffChunk']:
        """
        Splits this DiffChunk into multiple, smaller DiffChunks by calling the
        robust extract method for each segment.
        
        Args:
            split_indices: A list of indices into the ai_content list where the
                        splits should occur. The indices should be within the
                        valid range of the ai_content list.
        
        Returns:
            A list of new DiffChunk objects, each representing a valid sub-chunk.
        """
        # 1. Create a full list of boundary points for slicing.
        # We add 0 as the starting boundary and the total length as the final boundary.
        # Sorting and using a set handles cases where split_indices might be unsorted or contain duplicates.
        boundary_points = sorted(list(set([0] + split_indices + [len(self.ai_content)])))
        
        new_chunks = []
        
        # 2. Iterate through the boundary points to create start and end pairs.
        for i in range(len(boundary_points) - 1):
            start_index = boundary_points[i]
            end_index = boundary_points[i+1]
            
            # If start and end are the same, it means an empty slice was created
            # (e.g., from duplicate split points), so we can skip it.
            if start_index >= end_index:
                continue
            
            # 3. Call the robust `extract` method for each segment.
            sub_chunk = self.extract(start=start_index, end=end_index)
            
            # 4. The extract method returns a valid chunk or None. Only append valid chunks.
            if sub_chunk:
                new_chunks.append(sub_chunk)
                
        return new_chunks
    
    def extract(self, start: int, end: int) -> Optional['DiffChunk']:
        """
        Extracts a smaller, valid DiffChunk from this DiffChunk.
        
        Args:
            start: (Inclusive) The start index into ai_content.
            end: (Exclusive) The end index into ai_content.
        
        Returns:
            A new, valid DiffChunk object, or None if the slice is empty.
        """
        if not (0 <= start < end <= len(self.ai_content)):
            raise ValueError("Invalid start/end range for extraction.")
        
        sub_ai_content = self.ai_content[start:end]
        if not sub_ai_content:
            return None

        # 1. Separate additions and removals from the new slice
        sub_removals = [item for item in sub_ai_content if isinstance(item, Removal)]
        sub_additions = [item for item in sub_ai_content if isinstance(item, Addition)]

        # 2. Recalculate the raw content string for the new chunk
        new_content_lines = []
        for item in sub_ai_content:
            if isinstance(item, Addition):
                new_content_lines.append(f"+{item.content}")
            elif isinstance(item, Removal):
                new_content_lines.append(f"-{item.content}")
        new_content = "\n".join(new_content_lines)

        # 3. Determine the start lines and counts for the new header
        
        new_old_start = 0
        new_new_start = 0


        if sub_removals:
            # If there are removals, the start line is simply the line number of the first removal.
            new_old_start = sub_removals[0].line_number
        else:
            # For a pure addition, the insertion point is the line *after* the previous line.
            # In a `x,0` diff, the number refers to the line *before* the change.
            new_old_start = sub_additions[0].line_number-1

        if sub_additions:
            # If there are additions, the start line is the line number of the first addition.
            new_new_start = sub_additions[0].line_number
        else:        
            # For a pure removal, the insertion point in the new file is what remains.
            new_new_start = sub_removals[0].line_number-1

        return DiffChunk(
            file_path=self.file_path,
            content=new_content,
            ai_content=sub_ai_content,
            old_start=new_old_start,
            new_start=new_new_start,
        )
    
    def extract_by_lines(self, start_line: int, end_line: int) -> Optional['DiffChunk']:
        # Include all ai_content whose line_number falls in [start_line, end_line]
        sub_ai_content = [
            item for item in self.ai_content
            if start_line <= item.line_number <= end_line
        ]
        if not sub_ai_content:
            return None

        # compute old_start / new_start as before
        sub_removals = [r for r in sub_ai_content if isinstance(r, Removal)]
        sub_additions = [a for a in sub_ai_content if isinstance(a, Addition)]

        old_start = sub_removals[0].line_number if sub_removals else sub_additions[0].line_number - 1
        new_start = sub_additions[0].line_number if sub_additions else sub_removals[0].line_number - 1

        # reconstruct content string
        content_lines = [("+" if isinstance(i, Addition) else "-") + i.content for i in sub_ai_content]
        content_str = "\n".join(content_lines)

        return StandardDiffChunk(
            file_path=self.file_path,
            content=content_str,
            ai_content=sub_ai_content,
            old_start=old_start,
            new_start=new_start
        )
    
    def get_min_line(self):
        return min(self.ai_content, key = lambda c : c.line_number).line_number

    def get_max_line(self):
        return max(self.ai_content, key = lambda c : c.line_number).line_number
    
    def get_total_lines(self):
        return self.get_max_line() - self.get_min_line() + 1

    # override
    def format_json(
        self
    ) -> str:
        """
        Converts a list of structured diff objects into a standardized JSON format 
        optimized for LLM comprehension.

        Args:
            file_path: The path of the file being modified.
            change_list: The list of Addition, Removal, Move, or Replacement objects.

        Returns:
            A JSON string representing the structured diff.
        """
        w_moves = self.detect_moves(self.ai_content)
        simplified_diff = self.detect_replacements(w_moves)

        structured_changes = []

        for change in simplified_diff:
            change_dict = {}

            if isinstance(change, Addition):
                change_dict = {
                    "type": "Addition",
                    "line_number": change.line_number,
                    "content": change.content
                }
            
            elif isinstance(change, Removal):
                change_dict = {
                    "type": "Removal",
                    "line_number": change.line_number, # Line number in the old file state
                    "content": change.content
                }
                
            elif isinstance(change, Move):
                change_dict = {
                    "type": "Move",
                    "from_line": change.from_line,
                    "to_line": change.to_line,
                    "content": change.content
                }
                
            elif isinstance(change, Replacement):
                change_dict = {
                    "type": "Replacement",
                    "line_number": change.line_number,
                    "old_content": change.old_content,
                    "new_content": change.new_content
                }
            
            else:
                # Skip or log unknown types
                continue

            structured_changes.append(change_dict)

        # Wrap the changes into the final LLM-optimized JSON structure

        output_data = {
                "file_path": self.file_path,
                "changes": structured_changes
            }
        
        # Return the JSON string, using indentation for human readability 
        # (though LLMs can handle non-indented JSON equally well).
        return json.dumps(output_data, indent=2)
    
    @staticmethod
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

    @staticmethod
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
    
    @staticmethod
    def from_patch(file_path: str, patch_lines: List[str], old_start: int, new_start: int) -> "StandardDiffChunk":
        """
        Construct a StandardDiffChunk from patch lines (after @@ header).
        Generates ai_content automatically.
        """
        ai_content: List[Union[Addition, Removal]] = []
        current_old_line = old_start
        current_new_line = new_start

        content_lines = []

        for line in patch_lines:
            if line.startswith('+'):
                ai_content.append(Addition(content=line[1:], line_number=current_new_line))
                current_new_line += 1
                content_lines.append(line)
            elif line.startswith('-'):
                ai_content.append(Removal(content=line[1:], line_number=current_old_line))
                current_old_line += 1
                content_lines.append(line)

        raw_content = "\n".join(content_lines)
        return StandardDiffChunk(
            file_path=file_path,
            content=raw_content,
            ai_content=ai_content,
            old_start=old_start,
            new_start=new_start,
        )