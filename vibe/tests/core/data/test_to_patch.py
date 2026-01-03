import pytest

from vibe.core.data.models import Removal, Addition, DiffChunk

def test_to_patch_simple_addition_and_removal():
    """Tests a chunk with both additions and removals."""
    chunk = DiffChunk(
        file_path="file.py",
        content="-old line 1\n+new line 1\n-old line 2\n+new line 2",
        ai_content=[
            Removal(1, "old line 1"),
            Addition(1, "new line 1"),
            Removal(2, "old line 2"),
            Addition(2, "new line 2")
        ],
        old_start=1, old_end=2, new_start=1, new_end=2
    )
    expected_patch = (
        "--- a/file.py\n+++ b/file.py\n"
        "@@ -1,2 +1,2 @@\n"
        "-old line 1\n+new line 1\n-old line 2\n+new line 2"
    )
    assert chunk.to_patch() == expected_patch

def test_to_patch_only_additions():
    """Tests a chunk with only additions."""
    chunk = DiffChunk(
        file_path="new_file.txt",
        content="+line A\n+line B\n+line C",
        ai_content=[
            Addition(1, "line A"),
            Addition(2, "line B"),
            Addition(3, "line C")
        ],
        old_start=0, old_end=-1, new_start=1, new_end=3 # Common for new files
    )
    expected_patch = (
        "--- a/new_file.txt\n+++ b/new_file.txt\n"
        "@@ -0 +1,3 @@\n" # old_end - old_start + 1 = -1 - 0 + 1 = 0
        "+line A\n+line B\n+line C"
    )
    assert chunk.to_patch() == expected_patch

def test_to_patch_only_removals():
    """Tests a chunk with only removals."""
    chunk = DiffChunk(
        file_path="old_file.md",
        content="-removed line 1\n-removed line 2",
        ai_content=[
            Removal(1, "removed line 1"),
            Removal(2, "removed line 2")
        ],
        old_start=1, old_end=2, new_start=0, new_end=-1 # Common for deleted files
    )
    expected_patch = (
        "--- a/old_file.md\n+++ b/old_file.md\n"
        "@@ -1,2 +0 @@\n" # new_end - new_start + 1 = -1 - 0 + 1 = 0
        "-removed line 1\n-removed line 2"
    )
    assert chunk.to_patch() == expected_patch

def test_to_patch_empty_content_no_changes():
    """Tests a chunk representing no actual changes (empty content)."""
    # This scenario might not happen often for an actual 'chunk' but tests the edge.
    chunk = DiffChunk(
        file_path="empty.py",
        content="",
        ai_content=[],
        old_start=1, old_end=0, new_start=1, new_end=0 # Represents 0 lines changed
    )
    expected_patch = (
        "--- a/empty.py\n+++ b/empty.py\n"
        "@@ -1 +1 @@\n" # old_end - old_start + 1 = 0; new_end - new_start + 1 = 0
    )
    assert chunk.to_patch() == expected_patch

def test_to_patch_with_context_lines():
    """Tests a chunk that might implicitly have context lines (though content only shows +/-)."""
    # The `content` attribute is raw lines, so it's assumed to include context if any.
    # The `ai_content` only holds additions/removals.
    chunk = DiffChunk(
        file_path="context_file.js",
        content=" context line\n-removed\n+added\n context line 2",
        ai_content=[
            # Context lines are usually handled by the diffing tool,
            # but for this test, we demonstrate the content attribute.
            Removal(6, "removed"),
            Addition(6, "added")
        ],
        old_start=5, old_end=7, new_start=5, new_end=7
    )
    expected_patch = (
        "--- a/context_file.js\n+++ b/context_file.js\n"
        "@@ -5,3 +5,3 @@\n"
        " context line\n-removed\n+added\n context line 2"
    )
    assert chunk.to_patch() == expected_patch

def test_to_patch_missing_line_numbers_raises_error():
    """Tests that a ValueError is raised if old/new start/end are not set."""
    with pytest.raises(TypeError):
        DiffChunk(
            file_path="incomplete.py",
            start_line=1, end_line=1, content="+test", ai_content=[Addition(1, "test")]
            # Missing old_start, old_end, new_start, new_end
        )

def test_to_patch_single_line_change():
    """Tests a chunk with a single line replacement (R, A)."""
    chunk = DiffChunk(
        file_path="single_line.py",
        content="-old_code\n+new_code",
        ai_content=[
            Removal(5, "old_code"),
            Addition(5, "new_code")
        ],
        old_start=5, old_end=5, new_start=5, new_end=5
    )
    expected_patch = (
        "--- a/single_line.py\n+++ b/single_line.py\n"
        "@@ -5,1 +5,1 @@\n"
        "-old_code\n+new_code"
    )
    assert chunk.to_patch() == expected_patch