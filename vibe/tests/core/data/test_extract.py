import pytest
from vibe.core.data.models import Removal, Addition, DiffChunk

def setup_extract_chunk():
    """Helper to create a common complex DiffChunk for testing extractions."""
    ai_content_list = [
        Removal(1, "R1"), # Index 0
        Addition(1, "A1"), # Index 1
        Removal(2, "R2"), # Index 2
        Addition(3, "A3"), # Index 3
        Removal(4, "R4"), # Index 4
        Addition(5, "A5"), # Index 5
        Addition(6, "A6"), # Index 6
        Removal(7, "R7"), # Index 7
    ]
    raw_content = "-R1\n+A1\n-R2\n+A3\n-R4\n+A5\n+A6\n-R7"
    return DiffChunk(
        file_path="extract_file.py",
        content=raw_content,
        ai_content=ai_content_list,
        old_start=1, old_end=7, new_start=1, new_end=6
    )

def test_extract_middle_subchunk():
    """Extracts a sub-chunk from the middle of the original chunk."""
    original_chunk = setup_extract_chunk()
    # Extract from index 2 (R2) up to, but not including, index 5 (A5)
    extracted_chunk = original_chunk.extract(2, 5)
    assert extracted_chunk is not None
    assert extracted_chunk.content == "-R2\n+A3\n-R4"
    assert len(extracted_chunk.ai_content) == 3
    assert extracted_chunk.ai_content[0].content == "R2"
    assert extracted_chunk.ai_content[1].content == "A3"
    assert extracted_chunk.ai_content[2].content == "R4"

    # Verify calculated line numbers for the extracted patch
    assert extracted_chunk.old_start == 2
    assert extracted_chunk.old_end == 4
    assert extracted_chunk.new_start == 3
    assert extracted_chunk.new_end == 3


def test_extract_from_beginning_to_middle():
    """Extracts a sub-chunk starting from the first element."""
    original_chunk = setup_extract_chunk()
    # Extract from index 0 (R1) up to, but not including, index 3 (A3)
    extracted_chunk = original_chunk.extract(0, 3)
    assert extracted_chunk is not None
    assert extracted_chunk.content == "-R1\n+A1\n-R2"
    assert len(extracted_chunk.ai_content) == 3
    assert extracted_chunk.ai_content[0].content == "R1"
    assert extracted_chunk.ai_content[1].content == "A1"
    assert extracted_chunk.ai_content[2].content == "R2"

    assert extracted_chunk.old_start == 1
    assert extracted_chunk.old_end == 2
    assert extracted_chunk.new_start == 1
    assert extracted_chunk.new_end == 1

def test_extract_from_middle_to_end():
    """Extracts a sub-chunk ending with the last element."""
    original_chunk = setup_extract_chunk()
    # Extract from index 4 (R4) up to the end (index 8)
    extracted_chunk = original_chunk.extract(4, len(original_chunk.ai_content))
    assert extracted_chunk is not None
    assert extracted_chunk.content == "-R4\n+A5\n+A6\n-R7"
    assert len(extracted_chunk.ai_content) == 4
    assert extracted_chunk.ai_content[0].content == "R4"
    assert extracted_chunk.ai_content[1].content == "A5"
    assert extracted_chunk.ai_content[2].content == "A6"
    assert extracted_chunk.ai_content[3].content == "R7"

    assert extracted_chunk.old_start == 4
    assert extracted_chunk.old_end == 7
    assert extracted_chunk.new_start == 5
    assert extracted_chunk.new_end == 6

def test_extract_entire_chunk():
    """Extracting the whole chunk should yield a new chunk identical to the original."""
    original_chunk = setup_extract_chunk()
    extracted_chunk = original_chunk.extract(0, len(original_chunk.ai_content))
    assert extracted_chunk is not None
    assert extracted_chunk.file_path == original_chunk.file_path
    assert extracted_chunk.content == original_chunk.content
    assert extracted_chunk.ai_content == original_chunk.ai_content # List equality for content
    assert extracted_chunk.old_start == original_chunk.old_start
    assert extracted_chunk.old_end == original_chunk.old_end
    assert extracted_chunk.new_start == original_chunk.new_start
    assert extracted_chunk.new_end == original_chunk.new_end

def test_extract_empty_range_returns_none():
    """If start == end, an empty list is sliced, so None should be returned."""
    original_chunk = setup_extract_chunk()
    extracted_chunk = original_chunk.extract(2, 2)
    assert extracted_chunk is None

def test_extract_invalid_range_start_greater_than_end_returns_none():
    """If start > end, an empty list is sliced, so None should be returned."""
    original_chunk = setup_extract_chunk()
    extracted_chunk = original_chunk.extract(5, 2)
    assert extracted_chunk is None

def test_extract_out_of_bounds_indices():
    """Tests handling of indices that are out of bounds (Python slicing handles this)."""
    original_chunk = setup_extract_chunk()
    # Slice from before start to after end
    with pytest.raises(ValueError):
        original_chunk.extract(-5, len(original_chunk.ai_content) + 5)
    

    # Slice with only a valid part
    with pytest.raises(ValueError):
        original_chunk.extract(-2, 2) 
        

def test_extract_chunk_with_only_additions():
    """Extracts from a chunk containing only additions."""
    ai_content_list = [Addition(1, "A1"), Addition(2, "A2"), Addition(3, "A3")]
    original_chunk = DiffChunk(
        file_path="only_adds.py",
        content="+A1\n+A2\n+A3", ai_content=ai_content_list,
        old_start=0, old_end=-1, new_start=1, new_end=3
    )
    extracted_chunk = original_chunk.extract(1, 3) # A2, A3
    assert extracted_chunk is not None
    assert extracted_chunk.content == "+A2\n+A3"
    assert extracted_chunk.old_start == 0 and extracted_chunk.old_end == 0 # No old lines, so defaults
    assert extracted_chunk.new_start == 2 and extracted_chunk.new_end == 3

def test_extract_chunk_with_only_removals():
    """Extracts from a chunk containing only removals."""
    ai_content_list = [Removal(1, "R1"), Removal(2, "R2"), Removal(3, "R3")]
    original_chunk = DiffChunk(
        file_path="only_removes.py",
        content="-R1\n-R2\n-R3", ai_content=ai_content_list,
        old_start=1, old_end=3, new_start=0, new_end=-1
    )
    extracted_chunk = original_chunk.extract(0, 2) # R1, R2
    assert extracted_chunk is not None
    assert extracted_chunk.content == "-R1\n-R2"
    assert extracted_chunk.old_start == 1 and extracted_chunk.old_end == 2
    assert extracted_chunk.new_start == 0 and extracted_chunk.new_end == 0 # No new lines, so defaults

def test_extract_resulting_in_no_old_lines_but_new_lines():
    """Tests a scenario where the extracted chunk has additions but no removals."""
    original_chunk = setup_extract_chunk() # Has R and A
    extracted_chunk = original_chunk.extract(5, 7) # A5, A6
    assert extracted_chunk is not None
    assert extracted_chunk.content == "+A5\n+A6"
    assert extracted_chunk.old_start == original_chunk.old_start # Should default to parent or 0 if no old_lines
    assert extracted_chunk.old_end == original_chunk.old_start - 1 # Should default to parent's start - 1 or -1
    assert extracted_chunk.new_start == 5
    assert extracted_chunk.new_end == 6

def test_extract_resulting_in_no_new_lines_but_old_lines():
    """Tests a scenario where the extracted chunk has removals but no additions."""
    original_chunk = setup_extract_chunk() # Has R and A
    extracted_chunk = original_chunk.extract(0, 1) # R1
    assert extracted_chunk is not None
    assert extracted_chunk.content == "-R1"
    assert extracted_chunk.old_start == 1
    assert extracted_chunk.old_end == 1
    assert extracted_chunk.new_start == original_chunk.new_start # Should default to parent or 0
    assert extracted_chunk.new_end == original_chunk.new_start - 1 # Should default to parent's start - 1 or -1