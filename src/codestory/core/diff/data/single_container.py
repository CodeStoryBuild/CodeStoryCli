# -----------------------------------------------------------------------------
# /*
#  * Copyright (C) 2025 CodeStory
#  *
#  * This program is free software; you can redistribute it and/or modify
#  * it under the terms of the GNU General Public License as published by
#  * the Free Software Foundation; Version 2.
#  *
#  * This program is distributed in the hope that it will be useful,
#  * but WITHOUT ANY WARRANTY; without even the implied warranty of
#  * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  * GNU General Public License for more details.
#  *
#  * You should have received a copy of the GNU General Public License
#  * along with this program; if not, you can contact us at support@codestory.build
#  */
# -----------------------------------------------------------------------------

from dataclasses import dataclass

from codestory.core.diff.data.atomic_container import AtomicContainer


@dataclass(frozen=True)
class SingleContainer:
    """Represents a composite diff chunk that contains multiple atomic chunk instances.

    This allows grouping multiple related chunks together while maintaining the ability
    to process them as a single logical unit.

    Attributes:
        chunks: List of Chunk or ImmutableDiffChunk objects that make up this composite chunk
    """

    container: AtomicContainer

    def canonical_paths(self):
        """Return the canonical paths for this composite chunk."""
        return self.container.canonical_paths()

    def get_atomic_chunks(self) -> list:
        return self.container.get_atomic_chunks()
