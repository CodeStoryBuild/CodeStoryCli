from dataclasses import dataclass
from vibe.core.data.diff_chunk import DiffChunk
from typing import List, Optional, Callable


@dataclass
class LineNumbered:
    line_number: int
    content: str


@dataclass
class Addition(LineNumbered):
    """Represents a single added line of code."""

    ...


@dataclass
class Removal(LineNumbered):
    """Represents a single removed line of code."""

    ...


@dataclass(init=False)
class Move(LineNumbered):
    from_line: int
    to_line: int

    def __init__(self, content: str, from_line: int, to_line: int):
        self.content = content
        self.from_line = from_line
        self.to_line = to_line
        # line number will be the to_line in this case
        self.line_number = to_line


@dataclass(init=False)
class Replacement(LineNumbered):
    """Represents a line of code replaced with another, on the same line"""

    old_content: str
    new_content: str

    def __init__(self, old_content: str, new_content: str, line_number: int):
        self.old_content = old_content
        self.new_content = new_content
        self.content = new_content  # you can think of it as the final content state
        self.line_number = line_number


@dataclass
class CommitGroup:
    """
    A collection of DiffChunks that are committed together.
    """

    chunks: List[DiffChunk]
    group_id: str
    # branch_name: str
    commmit_message: str
    extended_message: Optional[str] = None


@dataclass
class CommitResult:
    """
    Result of a commit operation.
    """

    commit_hash: str
    group: CommitGroup


@dataclass(frozen=True)
class ChunkApplicationData:
    """A simplified, internal representation of a standard chunk's change data."""

    start_line: int
    line_count: int
    add_content: List[str]


@dataclass
class HunkWrapper:
    # new_file_path is the primary path for modifications or additions.
    new_file_path: str
    hunk_lines: List[str]
    old_start: int
    new_start: int
    old_len: int
    new_len: int
    # old_file_path is None unless this hunk is part of a rename.
    old_file_path: Optional[str] = None
    # file_mode is the mode of the new file (e.g., '100644', '100755')
    file_mode: Optional[str] = None
    # is_file_addition indicates this hunk is part of a new file being added
    is_file_addition: bool = False
    # is_file_deletion indicates this hunk is part of a file being deleted
    is_file_deletion: bool = False

    @property
    def is_rename(self) -> bool:
        return self.old_file_path is not None

    @property
    def file_path(self) -> str:
        # For backward compatibility or simple logic, provide a single file_path.
        return self.new_file_path


ProgressCallback = Callable[[int], None]
