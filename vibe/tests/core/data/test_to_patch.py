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
        old_start=1, new_start=1,
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
        old_start=0, new_start=1,
    )
    expected_patch = (
        "--- a/new_file.txt\n+++ b/new_file.txt\n"
        "@@ -0,0 +1,3 @@\n" 
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
        old_start=1, new_start=0# Common for deleted files
    )
    expected_patch = (
        "--- a/old_file.md\n+++ b/old_file.md\n"
        "@@ -1,2 +0,0 @@\n" 
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
        old_start=1, new_start=1,
    )
    expected_patch = (
        "--- a/empty.py\n+++ b/empty.py\n"
        "@@ -1,0 +1,0 @@\n" 
    )
    assert chunk.to_patch() == expected_patch


def test_to_patch_missing_line_numbers_raises_error():
    """Tests that a ValueError is raised if old/new start/end are not set."""
    with pytest.raises(TypeError):
        DiffChunk(
            file_path="incomplete.py",
            start_line=1, end_line=1, content="+test", ai_content=[Addition(1, "test")]
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
        old_start=5, new_start=5,
    )
    expected_patch = (
        "--- a/single_line.py\n+++ b/single_line.py\n"
        "@@ -5,1 +5,1 @@\n"
        "-old_code\n+new_code"
    )
    assert chunk.to_patch() == expected_patch

def test_to_patch_rename_with_modification():
    """Tests a DiffChunk representing a file rename plus a single line change."""
    chunk = DiffChunk(
        file_path="old_name.py",
        new_name="new_name.py",
        content="-old_line\n+new_line",
        ai_content=[
            Removal(3, "old_line"),
            Addition(3, "new_line")
        ],
        old_start=3,
        new_start=3,
    )

    expected_patch = (
        "rename from old_name.py\n"
        "rename to new_name.py\n"
        "@@ -3,1 +3,1 @@\n"
        "-old_line\n+new_line"
    )

    assert chunk.to_patch() == expected_patch
