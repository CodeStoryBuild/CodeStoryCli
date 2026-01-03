from typing import List, Callable
from .interface import ChunkerInterface
from ..data.models import DiffChunk
from ..data.s_diff_chunk import StandardDiffChunk


class PredicateChunker(ChunkerInterface):
    def __init__(self, split_predicate: Callable[[str], bool]):
        self.split_predicate = split_predicate

    def chunk(self, diff_chunks: List[DiffChunk]) -> List[DiffChunk]:
        result: List[DiffChunk] = []

        for chunk in diff_chunks:
            # only works with standard diff chunks
            if not isinstance(chunk, StandardDiffChunk):
                result.append(chunk)
                continue

            # start_num = line number of the first non-separator line in current piece
            # last_num  = line number of the most recent non-separator line seen
            start_num = None
            last_num = None

            for line in chunk.ai_content:
                ln = line.line_number
                if self.split_predicate(line.content):
                    # separator: close current piece if it contains at least one non-separator line
                    if start_num is not None and last_num is not None and last_num >= start_num:
                        sub_chunk = chunk.extract_by_lines(start_num, last_num)
                        if sub_chunk:
                            result.append(sub_chunk)
                    # reset to start a new piece after the separator(s)
                    start_num = None
                    last_num = None
                    continue

                # non-separator line: start or extend the current piece
                if start_num is None:
                    start_num = ln
                    last_num = ln
                else:
                    last_num = ln

            # end of hunk: flush any remaining piece
            if start_num is not None and last_num is not None and last_num >= start_num:
                sub_chunk = chunk.extract_by_lines(start_num, last_num)
                if sub_chunk:
                    result.append(sub_chunk)

        return result
