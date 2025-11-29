# -----------------------------------------------------------------------------
# codestory - Dual Licensed Software
# Copyright (c) 2025 Adem Can
#
# This file is part of codestory.
#
# codestory is available under a dual-license:
#   1. AGPLv3 (Affero General Public License v3)
#      - See LICENSE.txt and LICENSE-AGPL.txt
#      - Online: https://www.gnu.org/licenses/agpl-3.0.html
#
#   2. Commercial License
#      - For proprietary or revenue-generating use,
#        including SaaS, embedding in closed-source software,
#        or avoiding AGPL obligations.
#      - See LICENSE.txt and COMMERCIAL-LICENSE.txt
#      - Contact: ademfcan@gmail.com
#
# By using this file, you agree to the terms of one of the two licenses above.
# -----------------------------------------------------------------------------


from dataclasses import dataclass

from .chunk import Chunk


@dataclass(frozen=True)
class CompositeDiffChunk:
    """
    Represents a composite diff chunk that contains multiple DiffChunk instances.

    This allows grouping multiple related chunks together while maintaining the ability
    to process them as a single logical unit.

    Attributes:
        chunks: List of DiffChunk objects that make up this composite chunk
    """

    chunks: list[Chunk]

    def __post_init__(self):
        if len(self.chunks) <= 0:
            raise RuntimeError("Chunks must be a nonempty list!")

    def canonical_paths(self):
        """
        Return the canonical paths for this composite chunk.
        """
        paths = []

        for chunk in self.chunks:
            paths.extend(chunk.canonical_paths())

        return list(set(paths))

    def hunk_ranges(self) -> dict[bytes, list[tuple[int, int, int, int]]]:
        """
        Aggregate hunk ranges from all child chunks.

        Returns a dict keyed by canonical path (bytes) with lists of tuples
        describing (old_start, old_len, new_start, new_len). If multiple
        child chunks reference the same path, their ranges are concatenated.
        """
        aggregated: dict[bytes, list[tuple[int, int, int, int]]] = {}
        for chunk in self.chunks:
            for path, path_ranges in chunk.hunk_ranges().items():
                aggregated.setdefault(path, []).extend(path_ranges)

        return aggregated

    def get_chunks(self) -> list:
        chunks = []
        for chunk in self.chunks:
            chunks.extend(chunk.get_chunks())

        return chunks
