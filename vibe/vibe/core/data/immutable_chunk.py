from dataclasses import dataclass


@dataclass(frozen=True)
class ImmutableChunk:
    canonical_path: bytes
    file_patch: bytes
