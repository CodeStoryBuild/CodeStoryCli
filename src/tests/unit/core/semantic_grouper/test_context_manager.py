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

"""
Test script for ContextManager to validate it works correctly.
"""

from codestory.core.data.diff_chunk import DiffChunk
from codestory.core.data.line_changes import Addition, Removal
from codestory.core.semantic_grouper.context_manager import ContextManager


class MockFileReader:
    """Mock file reader for testing."""

    def __init__(self):
        # Mock file contents for testing
        self.files = {
            (
                "test.py",
                False,
            ): """def hello():
    print("Hello, World!")

class Calculator:
    def add(self, a, b):
        return a + b
""",
            (
                "test.py",
                True,
            ): """def hello():
    print("Hello, World!")

class Calculator:
    def add(self, a, b):
        return a + b
    
    def subtract(self, a, b):
        return a - b
""",
            (
                "new_file.py",
                False,
            ): """def new_function():
    return "This is new"
""",
        }

    def read(self, path: str, old_content: bool = False) -> str | None:
        """Read file content based on path and version."""
        return self.files.get((path, old_content))


def test_context_manager():
    """Test the ContextManager with various diff chunk types."""

    # Initialize components
    file_reader = MockFileReader()

    # Create test diff chunks
    diff_chunks = [
        # Standard modification
        DiffChunk(
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
        DiffChunk(
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

    # Create context manager
    context_manager = ContextManager(
        chunks=diff_chunks, file_reader=file_reader, fail_on_syntax_errors=False
    )

    # Test getting contexts
    # Test standard modification (should have both old and new versions)
    old_context = context_manager.get_context(b"test.py", True)
    assert old_context is not None, "Failed to get old version context for test.py"

    new_context = context_manager.get_context(b"test.py", False)
    assert new_context is not None, "Failed to get new version context for test.py"

    # Test file addition (should only have new version)
    new_file_context = context_manager.get_context(b"new_file.py", False)
    assert new_file_context is not None, "Failed to get context for new_file.py"

    old_file_context = context_manager.get_context(b"new_file.py", True)
    assert old_file_context is None, "Unexpectedly found old version for new_file.py"


if __name__ == "__main__":
    test_context_manager()
