# -----------------------------------------------------------------------------
# dslate - Dual Licensed Software
# Copyright (c) 2025 Adem Can
#
# This file is part of DSLATE.
#
# DSLATE is available under a dual-license:
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


from typing import Protocol, runtime_checkable

from .diff_chunk import DiffChunk


@runtime_checkable
class Chunk(Protocol):
    def canonical_paths(self) -> list[bytes]:
        """
        List of affected file paths that this chunk touches (as bytes).
        The canonical path is always the most relevant path for a chunk
        For file_additions/modifications/renames, it is the new file path
        For file_deletions it is the old file path
        """
        ...

    def get_chunks(self) -> list[DiffChunk]:
        """
        Get all diff chunks inside the chunk
        """
        ...
