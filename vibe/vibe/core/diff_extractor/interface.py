"""
DiffExtractorInterface

Responsibilities:
-----------------
- Extracts the current working diff from a Git repository.
- Produces a list of DiffChunk objects containing all information required to reconstruct patches.
- Filters out incomplete, erroneous, or generated files if needed.
- Acts as the primary source of raw changes for downstream pipeline steps.

Key Requirements for DiffChunk Output:
--------------------------------------
- file_path: original file path
- start_line / end_line: lines in the original file where the chunk appears
- old_start / old_end: line numbers in the previous version (for patch reconstruction)
- new_start / new_end: line numbers in the new version
- content: actual code lines in the chunk
- Must preserve enough context for the chunker to optionally split further into sub-hunks
- Must allow grouping and eventual patch-based commit creation

Possible Implementations:
-------------------------
- GitDiffExtractor: parses `git diff` output locally
- CustomDiffExtractor: user-defined filters, language-specific diff parsing
- AI-assisted DiffExtractor: uses AI to detect meaningful sub-hunks or filter noise

Notes:
------
- This interface provides the “raw input” for the rest of the pipeline: chunker, grouper, committer.
- Any splitting, AI analysis, or grouping should not lose metadata needed for patch reconstruction.
- Can optionally include metadata like file type, encoding, or flags to guide AI grouping.
"""

from abc import ABC, abstractmethod
from typing import List
from ..data.models import DiffChunk
from ..git_interface.interface import GitInterface

class DiffExtractorInterface(ABC):
    @abstractmethod
    def extract_diff(self, git_interface: GitInterface) -> List[DiffChunk]:
        """Return a list of raw hunks or diff chunks"""
