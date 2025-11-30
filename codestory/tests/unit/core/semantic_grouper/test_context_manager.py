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


"""
Test script for ContextManager to validate it works correctly.
"""

from codestory.core.data.diff_chunk import DiffChunk
from codestory.core.data.line_changes import Addition, Removal
from codestory.core.file_reader.file_parser import FileParser
from codestory.core.semantic_grouper.context_manager import ContextManager
from codestory.core.semantic_grouper.query_manager import QueryManager


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
    file_parser = FileParser()
    file_reader = MockFileReader()
    query_manager = QueryManager()

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
        file_parser=file_parser,
        file_reader=file_reader,
        query_manager=query_manager,
        diff_chunks=diff_chunks,
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
