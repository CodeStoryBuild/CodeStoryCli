from dataclasses import dataclass


@dataclass(frozen=True)
class ImmutableHunkWrapper:
    canonical_path: bytes
    file_patch: bytes
