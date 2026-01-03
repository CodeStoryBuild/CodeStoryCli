from typing import List, Callable
from .interface import ChunkerInterface
from ..data.models import DiffChunk
from ..data.s_diff_chunk import StandardDiffChunk
from ..data.c_diff_chunk import CompositeDiffChunk


class PredicateChunker(ChunkerInterface):
    def __init__(self, split_predicate: Callable[[str], bool]):
        self.split_predicate = split_predicate

    def chunk(self, diff_chunks: List[DiffChunk]) -> List[DiffChunk]:
        result: List[DiffChunk] = []

        for chunk in diff_chunks:
            if not isinstance(chunk, StandardDiffChunk):
                result.append(chunk)
                continue

            # Split into atomic chunks first
            atomic_chunks = ChunkerInterface.split_into_atomic_chunks(chunk)

            # Group atomic chunks based on predicate
            current_group: List[StandardDiffChunk] = []
            separator_group: List[StandardDiffChunk] = []

            for atomic_chunk in atomic_chunks:
                # Check if any line in the atomic chunk matches the predicate
                matches_predicate = any(
                    self.split_predicate(item.content)
                    for item in atomic_chunk.parsed_content
                )

                if matches_predicate:
                    # Flush any current group before starting separator group
                    if current_group:
                        if len(current_group) == 1:
                            result.append(current_group[0])
                        else:
                            result.append(
                                CompositeDiffChunk(
                                    chunks=current_group, _file_path=chunk._file_path
                                )
                            )
                        current_group = []

                    # Add to separator group
                    separator_group.append(atomic_chunk)
                else:
                    # Flush separator group if we have one
                    if separator_group:
                        if len(separator_group) == 1:
                            result.append(separator_group[0])
                        else:
                            result.append(
                                CompositeDiffChunk(
                                    chunks=separator_group, _file_path=chunk._file_path
                                )
                            )
                        separator_group = []

                    # Add to current group
                    current_group.append(atomic_chunk)

            # Flush any remaining groups
            if separator_group:
                if len(separator_group) == 1:
                    result.append(separator_group[0])
                else:
                    result.append(
                        CompositeDiffChunk(
                            chunks=separator_group, _file_path=chunk._file_path
                        )
                    )

            if current_group:
                if len(current_group) == 1:
                    result.append(current_group[0])
                else:
                    result.append(
                        CompositeDiffChunk(
                            chunks=current_group, _file_path=chunk._file_path
                        )
                    )

        return result
