"""
Test script for ContextManager to validate it works correctly.
"""

from typing import Optional
from vibe.core.file_reader.protocol import FileReader
from vibe.core.file_reader.file_parser import FileParser
from vibe.core.data.diff_chunk import DiffChunk
from vibe.core.data.line_changes import Addition, Removal
from vibe.core.semantic_grouper.context_manager import ContextManager
from vibe.core.semantic_grouper.query_manager import QueryManager


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

    def read(self, path: str, old_content: bool = False) -> Optional[str]:
        """Read file content based on path and version."""
        return self.files.get((path, old_content))


def test_context_manager():
    """Test the ContextManager with various diff chunk types."""

    # Initialize components
    file_parser = FileParser()
    file_reader = MockFileReader()
    query_manager = QueryManager("language_config.json")

    # Create test diff chunks
    diff_chunks = [
        # Standard modification
        DiffChunk(
            old_file_path="test.py",
            new_file_path="test.py",
            file_mode="100644",
            parsed_content=[
                Removal(content="    def subtract(self, a, b):", line_number=8),
                Removal(content="        return a - b", line_number=9),
            ],
            old_start=8,
            new_start=8,
        ),
        # File addition
        DiffChunk(
            old_file_path=None,
            new_file_path="new_file.py",
            file_mode="100644",
            parsed_content=[
                Addition(content="def new_function():", line_number=1),
                Addition(content='    return "This is new"', line_number=2),
            ],
            old_start=0,
            new_start=1,
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
    print("=== Context Manager Test ===")

    # Test standard modification (should have both old and new versions)
    old_context = context_manager.get_context("test.py", True)
    new_context = context_manager.get_context("test.py", False)

    if old_context:
        print(f"✓ Old version of test.py: {old_context.parsed_file.detected_language}")
        print(f"  Scope map lines: {len(old_context.scope_map.scope_lines)}")
        print(f"  Symbol map lines: {len(old_context.symbol_map.line_symbols)}")
    else:
        print("✗ Failed to get old version context for test.py")

    if new_context:
        print(f"✓ New version of test.py: {new_context.parsed_file.detected_language}")
        print(f"  Scope map lines: {len(new_context.scope_map.scope_lines)}")
        print(f"  Symbol map lines: {len(new_context.symbol_map.line_symbols)}")
    else:
        print("✗ Failed to get new version context for test.py")

    # Test file addition (should only have new version)
    new_file_context = context_manager.get_context("new_file.py", False)
    old_file_context = context_manager.get_context("new_file.py", True)

    if new_file_context:
        print(
            f"✓ New file new_file.py: {new_file_context.parsed_file.detected_language}"
        )
    else:
        print("✗ Failed to get context for new_file.py")

    if old_file_context is None:
        print("✓ Correctly no old version for new_file.py")
    else:
        print("✗ Unexpectedly found old version for new_file.py")

    # Test summary methods
    print(f"\nRequired contexts: {len(context_manager.get_required_contexts())}")
    print(f"Available contexts: {len(context_manager.get_available_contexts())}")
    print(f"File paths: {context_manager.get_file_paths()}")

    print("\n=== Test Complete ===")


if __name__ == "__main__":
    test_context_manager()
