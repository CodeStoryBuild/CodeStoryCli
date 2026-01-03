from vibe.core.data.models import Removal, Addition, DiffChunk

def setup_complex_chunk():
    """Helper to create a common complex DiffChunk for testing splits."""
    ai_content_list = [
        Removal(1, "R1"),
        Addition(1, "A1"), # index 1
        Removal(2, "R2"),
        Addition(3, "A3"), # index 3
        Removal(4, "R4"),
        Addition(5, "A5"), # index 5
        Addition(6, "A6"), # index 6
        Removal(7, "R7"),
    ]
    raw_content = "-R1\n+A1\n-R2\n+A3\n-R4\n+A5\n+A6\n-R7"
    return DiffChunk(
        file_path="test_file.py",
        content=raw_content,
        ai_content=ai_content_list,
        old_start=1, new_start=1,
    )

def test_split_no_splits_returns_original_chunk_in_list():
    """If no split indices are provided, the original chunk (as a list) should be returned."""
    original_chunk = setup_complex_chunk()
    split_indices = []
    result = original_chunk.split(split_indices)
    assert len(result) == 1
    assert result[0].file_path == original_chunk.file_path
    assert result[0].content == original_chunk.content
    assert result[0].ai_content == original_chunk.ai_content
    assert result[0].old_start == original_chunk.old_start
    assert result[0].new_start == original_chunk.new_start

def test_split_in_middle_into_two_chunks():
    """Splits a chunk into two distinct parts."""
    original_chunk = setup_complex_chunk()
    # Split between Addition(3, "A3") (index 3) and Removal(4, "R4") (index 4)
    split_indices = [4] 
    result = original_chunk.split(split_indices)
    assert len(result) == 2

    # Verify first chunk
    assert result[0].content == "-R1\n+A1\n-R2\n+A3"
    assert len(result[0].ai_content) == 4
    assert result[0].old_start == 1
    assert result[0].new_start == 1

    # Verify second chunk
    assert result[1].content == "-R4\n+A5\n+A6\n-R7"
    assert len(result[1].ai_content) == 4
    assert result[1].old_start == 4
    assert result[1].new_start == 5


def test_split_at_beginning():
    """Splits at the very beginning, resulting in an empty first chunk (which should be skipped) and the rest."""
    original_chunk = setup_complex_chunk()
    split_indices = [0] # This should implicitly be handled by the [0] + split_indices logic
    result = original_chunk.split(split_indices)
    assert len(result) == 1 # The split at 0 means [0:0] which is empty, so only one chunk remains
    assert result[0].content == original_chunk.content
    assert result[0].ai_content == original_chunk.ai_content

def test_split_at_end():
    """Splits at the very end, resulting in the original chunk and an empty last chunk (skipped)."""
    original_chunk = setup_complex_chunk()
    split_indices = [len(original_chunk.ai_content)]
    result = original_chunk.split(split_indices)
    assert len(result) == 1
    assert result[0].content == original_chunk.content
    assert result[0].ai_content == original_chunk.ai_content

def test_split_multiple_times():
    """Splits a chunk into three or more parts."""
    original_chunk = setup_complex_chunk()
    # Split after A1 (index 2), and after A5 (index 6)
    split_indices = [2, 6]
    result = original_chunk.split(split_indices)
    assert len(result) == 3

    # Chunk 1: R1, A1
    assert result[0].content == "-R1\n+A1"

    # Chunk 2: R2, A3, R4, A5
    assert result[1].content == "-R2\n+A3\n-R4\n+A5"

    # Chunk 3: A6, R7
    assert result[2].content == "+A6\n-R7"

def test_split_with_empty_subchunks_filtered():
    """Splits that would result in empty sub-chunks should be filtered out."""
    original_chunk = setup_complex_chunk()
    # Indices 0, 1, 1, 2, 8 (len is 8)
    # This will create slices [0:0], [0:1], [1:1], [1:2], [2:8], [8:8]
    # Expect non-empty slices: [0:1], [1:2], [2:8]
    split_indices = [0, 1, 1, 2, len(original_chunk.ai_content)] # Deliberately redundant/edge
    result = original_chunk.split(split_indices)
    assert len(result) == 3 # R1; A1; R2, A3, R4, A5, A6, R7 (simplified due to logic)

    # Re-examine expected behavior for split_indices
    # [0] + split_indices + [len(self.ai_content)] becomes:
    # [0, 0, 1, 1, 2, 8, 8] -> sorted unique: [0, 1, 2, 8]
    # Slices:
    # [0:1] -> [R1]
    # [1:2] -> [A1]
    # [2:8] -> [R2, A3, R4, A5, A6, R7]

    assert len(result) == 3

    assert result[0].content == "-R1"
    assert result[0].ai_content == [Removal(1, "R1")]
    assert result[0].old_start == 1
    assert result[0].new_start == 0

    assert result[1].content == "+A1"
    assert result[1].ai_content == [Addition(1, "A1")]
    assert result[1].old_start == 0
    assert result[1].new_start == 1

    assert result[2].content == "-R2\n+A3\n-R4\n+A5\n+A6\n-R7"
    assert result[2].ai_content == [
        Removal(2, "R2"), Addition(3, "A3"), Removal(4, "R4"),
        Addition(5, "A5"), Addition(6, "A6"), Removal(7, "R7")
    ]
    assert result[2].old_start == 2
    assert result[2].new_start == 3

def test_split_chunk_with_only_additions():
    """Tests splitting a chunk that only contains additions."""
    ai_content_list = [Addition(1, "A1"), Addition(2, "A2"), Addition(3, "A3")]
    original_chunk = DiffChunk(
        file_path="only_adds.py",
        content="+A1\n+A2\n+A3", ai_content=ai_content_list,
        old_start=0, new_start=1,
    )
    split_indices = [1] # Split after A1
    result = original_chunk.split(split_indices)
    assert len(result) == 2

    assert result[0].content == "+A1"
    assert result[0].ai_content == [Addition(1, "A1")]
    assert result[0].old_start == 0
    assert result[0].new_start == 1

    assert result[1].content == "+A2\n+A3"
    assert result[1].ai_content == [Addition(2, "A2"), Addition(3, "A3")]
    assert result[1].old_start == 0
    assert result[1].new_start == 2

def test_split_chunk_with_only_removals():
    """Tests splitting a chunk that only contains removals."""
    ai_content_list = [Removal(1, "R1"), Removal(2, "R2"), Removal(3, "R3")]
    original_chunk = DiffChunk(
        file_path="only_removes.py",
        content="-R1\n-R2\n-R3", ai_content=ai_content_list,
        old_start=1, new_start=0,
    )
    split_indices = [2] # Split after R2
    result = original_chunk.split(split_indices)
    assert len(result) == 2

    assert result[0].content == "-R1\n-R2"
    assert result[0].ai_content == [Removal(1, "R1"), Removal(2, "R2")]
    assert result[0].old_start == 1
    assert result[0].new_start == 0

    assert result[1].content == "-R3"
    assert result[1].ai_content == [Removal(3, "R3")]
    assert result[1].old_start == 3
    assert result[1].new_start == 0

def test_split_with_duplicate_split_indices():
    """Ensures duplicate split indices are handled correctly (only one split per index)."""
    original_chunk = setup_complex_chunk()
    split_indices = [4, 4] # Duplicate index
    result = original_chunk.split(split_indices)
    assert len(result) == 2 # Should still result in two chunks as if split_indices was [4]

    assert result[0].content == "-R1\n+A1\n-R2\n+A3"
    assert result[1].content == "-R4\n+A5\n+A6\n-R7"

def test_split_with_out_of_order_split_indices():
    """Ensures out-of-order split indices are sorted and handled correctly."""
    original_chunk = setup_complex_chunk()
    split_indices = [6, 2] # Out of order
    result = original_chunk.split(split_indices)
    assert len(result) == 3 # Should sort to [2, 6] and produce three chunks

    # Chunk 1: R1, A1
    assert result[0].content == "-R1\n+A1"
    # Chunk 2: R2, A3, R4, A5
    assert result[1].content == "-R2\n+A3\n-R4\n+A5"
    # Chunk 3: A6, R7
    assert result[2].content == "+A6\n-R7"