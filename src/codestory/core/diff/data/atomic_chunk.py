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


@dataclass(frozen=True)
class AtomicDiffChunk:
    # The reference tip of where to apply the change
    base_hash: str
    # The reference of where new lines are from.
    # Will not be used much other than for getting file content
    new_hash: str

    old_file_path: bytes | None
    new_file_path: bytes | None

    def canonical_path(self) -> bytes:
        """Returns the canonical path for the chunk.

        Modifications/Renames: new_file_path
        Additions: new_file_path
        Deletions: old_file_path
        """
        if self.new_file_path is not None:
            return self.new_file_path
        else:
            return self.old_file_path

    @property
    def is_file_rename(self) -> bool:
        return (
            self.old_file_path is not None
            and self.new_file_path is not None
            and self.old_file_path != self.new_file_path
        )

    @property
    def is_standard_modification(self) -> bool:
        return (
            self.old_file_path == self.new_file_path and self.old_file_path is not None
        )

    @property
    def is_file_addition(self) -> bool:
        return self.old_file_path is None and self.new_file_path is not None

    @property
    def is_file_deletion(self) -> bool:
        return self.old_file_path is not None and self.new_file_path is None

    def canonical_paths(self) -> list[bytes]:
        return [self.canonical_path()]

    def get_atomic_chunks(self) -> list["AtomicDiffChunk"]:
        return [self]
