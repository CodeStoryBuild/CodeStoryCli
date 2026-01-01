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

"""Test script for ContextManager to validate it works correctly."""

from codestory.core.diff.data.line_changes import Addition, Removal
from codestory.core.diff.data.standard_diff_chunk import StandardDiffChunk
from codestory.core.semantic_analysis.annotation.context_manager import (
    ContextManagerBuilder,
)
from codestory.core.semantic_analysis.annotation.file_manager import FileManager


class MockFileManager(FileManager):
    """Mock file manager for testing that skips git_commands initialization."""

    def __init__(self):
        # Skip parent __init__ to avoid git_commands dependency
        self._content_cache: dict[tuple[bytes, str], bytes | None] = {}
        self._line_counts: dict[tuple[bytes, str], int | None] = {}
        self._lines_cache: dict[tuple[bytes, str], list[str]] = {}

        # Mock file contents for testing
        test_files = {
            (
                b"test.py",
                "base",
            ): b"""def hello():
    print("Hello, World!")

class Calculator:
    def add(self, a, b):
        return a + b
""",
            (
                b"test.py",
                "head",
            ): b"""def hello():
    print("Hello, World!")

class Calculator:
    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b
""",
            (
                b"new_file.py",
                "head",
            ): b"""def new_function():
    return "This is new"
""",
        }

        # Pre-populate cache
        for key, content in test_files.items():
            self._content_cache[key] = content
            self._line_counts[key] = len(content.splitlines())


def test_context_manager():
    """Test the ContextManager with various diff chunk types."""

    # Initialize components
    file_manager = MockFileManager()

    # Create test diff chunks
    diff_chunks = [
        # Standard modification
        StandardDiffChunk(
            base_hash="base",
            new_hash="head",
            old_file_path=b"test.py",
            new_file_path=b"test.py",
            file_mode=b"100644",
            parsed_content=[
                Removal(
                    content=b"    def subtract(self, a, b):", old_line=8, abs_new_line=8
                ),
                Removal(content=b"        return a - b", old_line=9, abs_new_line=9),
            ],
            old_start=8,
        ),
        # File addition
        StandardDiffChunk(
            base_hash="base",
            new_hash="head",
            old_file_path=None,
            new_file_path=b"new_file.py",
            file_mode=b"100644",
            parsed_content=[
                Addition(content=b"def new_function():", old_line=0, abs_new_line=1),
                Addition(
                    content=b'    return "This is new"', old_line=0, abs_new_line=2
                ),
            ],
            old_start=0,
        ),
    ]

    # Create context manager using builder
    context_manager = ContextManagerBuilder(
        chunks=diff_chunks,
        file_manager=file_manager,
        fail_on_syntax_errors=False,
    ).build()

    # Test getting contexts
    # Test standard modification (should have both old and new versions)
    old_context = context_manager.get_context(b"test.py", "base")
    assert old_context is not None, "Failed to get old version context for test.py"

    new_context = context_manager.get_context(b"test.py", "head")
    assert new_context is not None, "Failed to get new version context for test.py"

    # Test file addition (should only have new version)
    new_file_context = context_manager.get_context(b"new_file.py", "head")
    assert new_file_context is not None, "Failed to get context for new_file.py"

    old_file_context = context_manager.get_context(b"new_file.py", "base")
    assert old_file_context is None, "Unexpectedly found old version for new_file.py"


if __name__ == "__main__":
    test_context_manager()
