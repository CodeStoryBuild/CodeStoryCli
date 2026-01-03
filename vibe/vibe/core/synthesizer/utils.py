from itertools import groupby
from ..data.chunk import Chunk
from ..data.diff_chunk import DiffChunk
from ..data.models import CommitGroup
from .git_synthesizer import GitSynthesizer


def get_total_chunks_per_file(chunks: list[DiffChunk]):
    total_chunks_per_file = {}
    for file_path, file_chunks_iter in groupby(
        sorted(chunks, key=lambda c: c.canonical_path()),
        key=lambda c: c.canonical_path(),
    ):
        total_chunks_per_file[file_path] = len(list(file_chunks_iter))

    return total_chunks_per_file


def get_descriptive_patch(chunks: list[DiffChunk], total_chunks: dict[bytes, int]):
    diff = GitSynthesizer._generate_unified_diff(chunks, total_chunks)

    return b"\n\n".join(diff.values()).decode('utf-8', errors='replace')


def get_patches_chunk(chunks: list[Chunk]) -> dict[int, str]:
    flattened_chunks = []
    for chunk in chunks:
        flattened_chunks.extend(chunk.get_chunks())

    total_chunks_per_file = get_total_chunks_per_file(flattened_chunks)

    patch_map = {}
    for i, chunk in enumerate(chunks):
        patch_map[i] = get_descriptive_patch(chunk.get_chunks(), total_chunks_per_file)

    return patch_map


def get_patches(groups: list[CommitGroup]) -> dict[int, str]:
    flattened_chunks = []
    for group in groups:
        for chunk in group.chunks:
            flattened_chunks.extend(chunk.get_chunks())

    total_chunks_per_file = get_total_chunks_per_file(flattened_chunks)

    patch_map = {}
    for i, group in enumerate(groups):
        group_chunks = []
        for chunk in group.chunks:
            group_chunks.extend(chunk.get_chunks())
        patch_map[i] = get_descriptive_patch(group_chunks, total_chunks_per_file)

    return patch_map
