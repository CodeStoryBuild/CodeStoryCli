#!/usr/bin/env python3
"""
Test script for the SemanticGrouper implementation.
"""

import sys
import os

# Add the vibe module to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "vibe"))

from vibe.core.semantic_grouper.semantic_grouper import SemanticGrouper
from vibe.core.semantic_grouper.query_manager import QueryManager
from vibe.core.file_reader.file_parser import FileParser
from vibe.core.data.diff_chunk import DiffChunk
from vibe.core.data.line_changes import Addition, Removal


class MockFileReader:
    """Mock file reader for testing."""

    def __init__(self):
        self.file_contents = {
            # New version of fileA.py
            (
                "vibe_playground/fileA.py",
                False,
            ): """def calculate():
    return 42

print(calculate())

class Greeter:
    def say_hello(self):
        self.aa = 1 

    def say_bye(self):
        print(20)

def farewell():
    print("Goodbye")
""",
            # Old version of fileA.py (slightly different)
            (
                "vibe_playground/fileA.py",
                True,
            ): """def calculate():
    return 41

print(calculate())

class Greeter:
    def say_hello(self):
        self.aa = 1 

    def say_bye(self):
        print(20)

def farewell():
    print("Goodbye")
""",
        }

    def read(self, path: str, old_content: bool = False) -> str | None:
        return self.file_contents.get((path, old_content))


def create_test_chunks():
    """Create some test diff chunks."""

    # Chunk 1: Modification in calculate function (line 2)
    chunk1 = DiffChunk(
        old_file_path="vibe_playground/fileA.py",
        new_file_path="vibe_playground/fileA.py",
        file_mode="100644",
        parsed_content=[
            Removal(content="    return 41", line_number=2),
            Addition(content="    return 42", line_number=2),
        ],
        old_start=2,
        new_start=2,
    )

    # Chunk 2: Modification in say_hello method (line 8)
    chunk2 = DiffChunk(
        old_file_path="vibe_playground/fileA.py",
        new_file_path="vibe_playground/fileA.py",
        file_mode="100644",
        parsed_content=[Addition(content="        # Added comment", line_number=8)],
        old_start=7,
        new_start=8,
    )

    return [chunk1, chunk2]


def main():
    """Test the semantic grouper."""

    print("Testing SemanticGrouper...")

    # Set up components
    file_parser = FileParser()
    file_reader = MockFileReader()
    query_manager = QueryManager(
        "vibe/semantic_grouping/language_config/language_config.json"
    )

    # Create grouper
    grouper = SemanticGrouper(
        file_parser=file_parser, file_reader=file_reader, query_manager=query_manager
    )

    # Create test chunks
    chunks = create_test_chunks()

    print(f"Created {len(chunks)} test chunks")

    # Group the chunks
    try:
        semantic_groups = grouper.group_chunks(chunks)

        print(f"\nGenerated {len(semantic_groups)} semantic groups:")

        for i, group in enumerate(semantic_groups):
            print(
                f"  Group {i + 1}: {len(group.chunks)} chunks, fallback={group.is_fallback_group}"
            )

        print("\nTest completed successfully!")

    except Exception as e:
        print(f"Error during grouping: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
