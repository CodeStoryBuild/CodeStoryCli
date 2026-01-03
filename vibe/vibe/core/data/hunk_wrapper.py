from dataclasses import dataclass
from typing import List, Optional


@dataclass
class HunkWrapper:
    # new_file_path is the primary path for modifications or additions.
    new_file_path: Optional[bytes]
    old_file_path: Optional[bytes]
    hunk_lines: List[bytes]
    old_start: int
    new_start: int
    old_len: int
    new_len: int
    file_mode: Optional[bytes] = b"100644"  # default to regular file

    @property
    def is_rename(self) -> bool:
        return self.old_file_path is not None

    @property
    def file_path(self) -> Optional[bytes]:
        # For backward compatibility or simple logic, provide a single file_path.
        return self.new_file_path

    @staticmethod
    def create_empty_content(
        new_file_path: Optional[bytes], old_file_path: Optional[bytes], file_mode: Optional[bytes] = None
    ) -> "HunkWrapper":
        return HunkWrapper(
            new_file_path=new_file_path,
            old_file_path=old_file_path,
            hunk_lines=[],
            old_start=0,
            new_start=0,
            old_len=0,
            new_len=0,
            file_mode=file_mode,
        )

    @staticmethod
    def create_empty_addition(
        new_file_path: Optional[bytes], file_mode: Optional[bytes] = None
    ) -> "HunkWrapper":
        return HunkWrapper(
            new_file_path=new_file_path,
            old_file_path=None,
            hunk_lines=[],
            old_start=0,
            new_start=0,
            old_len=0,
            new_len=0,
            file_mode=file_mode,
        )

    @staticmethod
    def create_empty_deletion(
        old_file_path: Optional[bytes], file_mode: Optional[bytes] = None
    ) -> "HunkWrapper":
        return HunkWrapper(
            new_file_path=None,
            old_file_path=old_file_path,
            hunk_lines=[],
            old_start=0,
            new_start=0,
            old_len=0,
            new_len=0,
            file_mode=file_mode,
        )
