from typing import List, Callable
from .interface import ChunkerInterface
from ..data.diff_chunk import DiffChunk
from ..data.c_diff_chunk import CompositeDiffChunk


class PredicateChunker(ChunkerInterface):
    def __init__(self, split_predicate: Callable[[str], bool]):
        self.split_predicate = split_predicate

    def chunk(self, diff_chunks: List[DiffChunk]) -> List[DiffChunk]:
        result: List[DiffChunk] = []

        for chunk in diff_chunks:
            # Split into atomic chunks first
            atomic_chunks = chunk.split_into_atomic_chunks()

            # Group atomic chunks based on predicate
            current_group: List[DiffChunk] = []
            separator_group: List[DiffChunk] = []

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
                                    chunks=current_group,
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
                                    chunks=separator_group,
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
                            chunks=separator_group,
                        )
                    )

            if current_group:
                if len(current_group) == 1:
                    result.append(current_group[0])
                else:
                    result.append(
                        CompositeDiffChunk(
                            chunks=current_group,
                        )
                    )

        return result
