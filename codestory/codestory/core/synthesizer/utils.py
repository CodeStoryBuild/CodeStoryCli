# -----------------------------------------------------------------------------
# dslate - Dual Licensed Software
# Copyright (c) 2025 Adem Can
#
# This file is part of DSLATE.
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


from ..data.chunk import Chunk
from ..data.commit_group import CommitGroup
from ..data.immutable_chunk import ImmutableChunk
from .diff_generator import DiffGenerator


def get_patches_chunk(chunks: list[Chunk]) -> dict[int, str]:
    diff_generator = DiffGenerator(chunks)

    patch_map = {}
    for i, chunk in enumerate(chunks):
        patches = diff_generator.generate_unified_diff(chunk.get_chunks())

        if patches:
            # sort by file name
            ordered_items = sorted(patches.items(), key=lambda kv: kv[0])
            combined_patch = b"".join(patch for _, patch in ordered_items)
        else:
            combined_patch = ""

        patch_map[i] = combined_patch.decode("utf-8", errors="replace")

    return patch_map


def get_patches(groups: list[CommitGroup]) -> dict[int, str]:
    diff_generator = DiffGenerator(groups)

    patch_map = {}
    for i, group in enumerate(groups):
        group_chunks = []
        for chunk in group.chunks:
            if isinstance(chunk, ImmutableChunk):
                group_chunks.append(chunk)
            else:
                group_chunks.extend(chunk.get_chunks())

        patches = diff_generator.generate_unified_diff(group_chunks)

        if patches:
            # sort by file name
            ordered_items = sorted(patches.items(), key=lambda kv: kv[0])
            combined_patch = b"".join(patch for _, patch in ordered_items)
        else:
            combined_patch = b""

        patch_map[i] = combined_patch.decode("utf-8", errors="replace")

    return patch_map
