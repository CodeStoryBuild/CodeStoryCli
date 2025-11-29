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


@dataclass
class HunkWrapper:
    # new_file_path is the primary path for modifications or additions.
    new_file_path: bytes | None
    old_file_path: bytes | None
    hunk_lines: list[bytes]
    old_start: int
    new_start: int
    old_len: int
    new_len: int
    file_mode: bytes | None = b"100644"  # default to regular file

    @property
    def file_path(self) -> bytes | None:
        # For backward compatibility or simple logic, provide a single file_path.
        return self.new_file_path

    @staticmethod
    def create_empty_content(
        new_file_path: bytes | None,
        old_file_path: bytes | None,
        file_mode: bytes | None = None,
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
        new_file_path: bytes | None, file_mode: bytes | None = None
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
        old_file_path: bytes | None, file_mode: bytes | None = None
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
