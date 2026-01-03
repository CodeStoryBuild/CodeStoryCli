from collections import defaultdict
from typing import List, Optional, Tuple

from ..data.s_diff_chunk import StandardDiffChunk
from ..data.models import Addition, Removal


def chunks_disjoint(chunks: List[StandardDiffChunk]) -> bool:
    """
    Returns True if all diff chunks are fully disjoint.

    Disjoint is defined on a per-file basis:
    1. For any given file, no two chunks touch or overlap the same line numbers
       in the old version of the file.
    2. For any given file, no two chunks touch or overlap the same line numbers
       in the new version of the file.

    Chunks from different files are always considered disjoint from each other.
    """

    def _get_inclusive_ranges(
        chunk: StandardDiffChunk,
    ) -> Tuple[Optional[Tuple[int, int]], Optional[Tuple[int, int]]]:
        """Return (old_start, old_end), (new_start, new_end) inclusive ranges."""
        old_lines = [
            i.line_number for i in chunk.parsed_content if isinstance(i, Removal)
        ]
        new_lines = [
            i.line_number for i in chunk.parsed_content if isinstance(i, Addition)
        ]

        old_range = (min(old_lines), max(old_lines)) if old_lines else None
        new_range = (min(new_lines), max(new_lines)) if new_lines else None
        return old_range, new_range

    def _check_no_overlap(ranges: List[Tuple[int, int]]) -> bool:
        """
        Check that no ranges in the sorted list overlap.
        Ranges are inclusive [start, end].
        """
        if len(ranges) < 2:
            return True

        sorted_ranges = sorted(ranges)

        for i in range(len(sorted_ranges) - 1):
            prev_end = sorted_ranges[i][1]
            cur_start = sorted_ranges[i + 1][0]

            # For inclusive ranges [s1, e1] and [s2, e2], they overlap if s2 <= e1.
            if cur_start <= prev_end:
                return False
        return True

    # Use defaultdict to group ranges by file path
    old_ranges_by_file = defaultdict(list)
    new_ranges_by_file = defaultdict(list)

    # Phase 1: Group all ranges by file
    for chunk in chunks:
        o_range, n_range = _get_inclusive_ranges(chunk)
        if o_range:
            old_ranges_by_file[chunk._file_path].append(o_range)
        if n_range:
            new_ranges_by_file[chunk._file_path].append(n_range)

    # Phase 2: Check for overlaps within each file's range list
    all_old_disjoint = all(
        _check_no_overlap(ranges) for ranges in old_ranges_by_file.values()
    )
    all_new_disjoint = all(
        _check_no_overlap(ranges) for ranges in new_ranges_by_file.values()
    )

    return all_old_disjoint and all_new_disjoint
