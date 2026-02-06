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

from codestory.core.diff.data.line_changes import Addition, Removal
from codestory.core.diff.data.standard_diff_chunk import StandardDiffChunk
from codestory.core.diff.patch.semantic_patch_generator import SemanticPatchGenerator


class MockFileManager:
    def __init__(self):
        self._lines = {
            (b"old.py", "base"): ["line1", "line2", "line3"],
        }

    def get_file_lines(self, file_path: bytes, commit_hash: str) -> list[str]:
        return self._lines.get((file_path, commit_hash), [])

    def get_line_count(self, file_path: bytes, commit_hash: str) -> int | None:
        lines = self._lines.get((file_path, commit_hash))
        if lines is None:
            return None
        return len(lines)


def test_semantic_patch_rename_uses_old_path_for_context():
    chunk = StandardDiffChunk(
        base_hash="base",
        new_hash="head",
        old_file_path=b"old.py",
        new_file_path=b"new.py",
        parsed_content=[
            Removal(old_line=2, abs_new_line=2, content=b"line2"),
            Addition(old_line=2, abs_new_line=2, content=b"line2_new"),
        ],
        old_start=2,
    )

    fm = MockFileManager()
    gen = SemanticPatchGenerator(
        containers=[chunk],
        file_manager=fm,
        context_lines=1,
        skip_whitespace=False,
    )

    patch = gen.get_patch(chunk)
    assert "[ctx] line1" in patch


def test_semantic_patch_preserves_old_start_zero():
    chunk = StandardDiffChunk(
        base_hash="base",
        new_hash="head",
        old_file_path=b"old.py",
        new_file_path=b"old.py",
        parsed_content=[
            Addition(old_line=0, abs_new_line=1, content=b"line0_new"),
        ],
        old_start=0,
    )

    fm = MockFileManager()
    gen = SemanticPatchGenerator(
        containers=[chunk],
        file_manager=fm,
        context_lines=1,
        skip_whitespace=False,
    )

    patch = gen.get_patch(chunk)
    assert "[h] Line 0:" in patch
