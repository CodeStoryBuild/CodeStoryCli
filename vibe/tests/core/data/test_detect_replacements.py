from vibe.core.data.models import Addition, Removal, Move, Replacement, ExtendedDiffChunk


def test_detect_replacements_simple_replacement():
    """Detects a single replacement."""
    input_changes = [
        Removal(1, "old line content"),
        Addition(1, "new line content")
    ]
    output = ExtendedDiffChunk.detect_replacements(input_changes)
    assert len(output) == 1
    assert isinstance(output[0], Replacement)
    assert output[0].old_content == "old line content"
    assert output[0].new_content == "new line content"
    assert output[0].line_number == 1

def test_detect_replacements_no_replacements_only_additions():
    """No removals present, so no replacements can occur."""
    input_changes = [
        Addition(1, "line A"),
        Addition(2, "line B")
    ]
    output = ExtendedDiffChunk.detect_replacements(input_changes)
    assert len(output) == 2
    assert isinstance(output[0], Addition)
    assert isinstance(output[1], Addition)
    assert output[0].content == "line A"
    assert output[1].content == "line B"

def test_detect_replacements_no_replacements_only_removals():
    """No additions to pair with removals, so no replacements can occur."""
    input_changes = [
        Removal(1, "line A"),
        Removal(2, "line B")
    ]
    output = ExtendedDiffChunk.detect_replacements(input_changes)
    assert len(output) == 2
    assert isinstance(output[0], Removal)
    assert isinstance(output[1], Removal)
    assert output[0].content == "line A"
    assert output[1].content == "line B"

def test_detect_replacements_multiple_replacements():
    """Detects multiple consecutive replacements."""
    input_changes = [
        Removal(1, "old 1"),
        Addition(1, "new 1"),
        Removal(2, "old 2"),
        Addition(2, "new 2")
    ]
    output = ExtendedDiffChunk.detect_replacements(input_changes)
    assert len(output) == 2
    assert isinstance(output[0], Replacement)
    assert output[0].old_content == "old 1"
    assert output[0].new_content == "new 1"
    assert output[0].line_number == 1
    assert isinstance(output[1], Replacement)
    assert output[1].old_content == "old 2"
    assert output[1].new_content == "new 2"
    assert output[1].line_number == 2

def test_detect_replacements_intervening_move():
    """A move operation between a removal and addition prevents replacement."""
    input_changes = [
        Removal(1, "line A"),
        Move(content="line M", from_line=5, to_line=2), # Intervening move
        Addition(3, "line A") # This should now be an Addition, not part of replacement
    ]
    output = ExtendedDiffChunk.detect_replacements(input_changes)
    assert len(output) == 3
    assert isinstance(output[0], Removal) and output[0].content == "line A"
    assert isinstance(output[1], Move) and output[1].content == "line M"
    assert isinstance(output[2], Addition) and output[2].content == "line A"

def test_detect_replacements_mixed_changes():
    """A complex mix of additions, removals, moves, and replacements."""
    input_changes = [
        Removal(1, "old_A"),
        Addition(1, "new_A"),      # Replacement 1
        Addition(2, "standalone_add"),
        Removal(3, "old_B"),
        Addition(3, "new_B"),      # Replacement 2
        Move(content="moved_line", from_line=10, to_line=4),
        Removal(5, "standalone_removal"),
        Removal(6, "old_C"),       # No matching addition for this one
    ]
    output = ExtendedDiffChunk.detect_replacements(input_changes)
    assert len(output) == 6
    assert isinstance(output[0], Replacement) and output[0].old_content == "old_A" and output[0].new_content == "new_A" and output[0].line_number == 1
    assert isinstance(output[1], Addition) and output[1].content == "standalone_add" and output[1].line_number == 2
    assert isinstance(output[2], Replacement) and output[2].old_content == "old_B" and output[2].new_content == "new_B" and output[2].line_number == 3
    assert isinstance(output[3], Move) and output[3].content == "moved_line" and output[3].to_line == 4 # line_number is to_line for Move
    assert isinstance(output[4], Removal) and output[4].content == "standalone_removal" and output[4].line_number == 5
    assert isinstance(output[5], Removal) and output[5].content == "old_C" and output[5].line_number == 6


def test_detect_replacements_end_of_list_removal():
    """A removal at the very end of the list should not form a replacement."""
    input_changes = [
        Addition(1, "line A"),
        Removal(2, "line B") # No addition after this
    ]
    output = ExtendedDiffChunk.detect_replacements(input_changes)
    assert len(output) == 2
    assert isinstance(output[0], Addition) and output[0].content == "line A"
    assert isinstance(output[1], Removal) and output[1].content == "line B"

def test_detect_replacements_start_of_list_addition():
    """An addition at the start should not be part of a replacement unless preceded by a removal."""
    input_changes = [
        Addition(1, "line A"),
        Removal(2, "line B")
    ]
    output = ExtendedDiffChunk.detect_replacements(input_changes)
    assert len(output) == 2
    assert isinstance(output[0], Addition) and output[0].content == "line A"
    assert isinstance(output[1], Removal) and output[1].content == "line B"

def test_detect_replacements_empty_input():
    """Handles an empty list of changes."""
    input_changes = []
    output = ExtendedDiffChunk.detect_replacements(input_changes)
    assert output == []

def test_detect_replacements_replacement_with_same_content():
    """If content is technically "replaced" with itself, it's still a Replacement by the function's logic."""
    input_changes = [
        Removal(1, "same content"),
        Addition(1, "same content")
    ]
    output = ExtendedDiffChunk.detect_replacements(input_changes)
    assert len(output) == 1
    assert isinstance(output[0], Replacement)
    assert output[0].old_content == "same content"
    assert output[0].new_content == "same content"
    assert output[0].line_number == 1

def test_detect_replacements_multiple_removals_then_addition():
    """
    R, R, A: The first removal should not be part of a replacement with the A.
    The function strictly looks for R followed *immediately* by A.
    """
    input_changes = [
        Removal(1, "old 1"),
        Removal(2, "old 2"),
        Addition(3, "new")
    ]
    output = ExtendedDiffChunk.detect_replacements(input_changes)
    assert len(output) == 3
    assert isinstance(output[0], Removal) and output[0].content == "old 1"
    assert isinstance(output[1], Removal) and output[1].content == "old 2"
    assert isinstance(output[2], Addition) and output[2].content == "new"

def test_detect_replacements_removal_then_addition_then_other():
    """Ensures a replacement is correctly identified and the following items are processed."""
    input_changes = [
        Removal(1, "R1"),
        Addition(1, "A1"), # Replacement
        Removal(2, "R2"),
        Addition(3, "A3_standalone")
    ]
    output = ExtendedDiffChunk.detect_replacements(input_changes)
    assert len(output) == 3
    assert isinstance(output[0], Replacement) and output[0].old_content == "R1" and output[0].new_content == "A1"
    assert isinstance(output[1], Removal) and output[1].content == "R2"
    assert isinstance(output[2], Addition) and output[2].content == "A3_standalone"

def test_detect_replacements_only_move():
    """A list containing only moves should pass through unchanged."""
    input_changes = [
        Move(content="M1", from_line=1, to_line=10),
        Move(content="M2", from_line=2, to_line=11)
    ]
    output = ExtendedDiffChunk.detect_replacements(input_changes)
    assert len(output) == 2
    assert isinstance(output[0], Move) and output[0].content == "M1"
    assert isinstance(output[1], Move) and output[1].content == "M2"

def test_detect_replacements_last_element_removal():
    """Tests when the list ends with a Removal, which cannot form a replacement."""
    input_changes = [
        Addition(1, "add"),
        Removal(2, "remove")
    ]
    output = ExtendedDiffChunk.detect_replacements(input_changes)
    assert len(output) == 2
    assert isinstance(output[0], Addition)
    assert isinstance(output[1], Removal)