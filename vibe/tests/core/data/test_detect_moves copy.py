from vibe.core.data.models import Addition, Removal, Move, Replacement, detect_moves


def test_detect_moves_simple_move_up():
    # simple move line of code up from line 2 -> 1
    input = [Addition(1, "test"), Removal (2, "test")]
    out = detect_moves(input)
    assert len(out) == 1
    assert isinstance(out[0], Move)
    assert out[0].content == "test"
    assert out[0].to_line == 1
    assert out[0].from_line == 2

def test_detect_moves_simple_move_down():
    # simple move line of code down from line 1 -> 2
    input = [Removal (1, "test"), Addition(2, "test")]
    out = detect_moves(input)
    assert len(out) == 1
    assert isinstance(out[0], Move)
    assert out[0].content == "test"
    assert out[0].to_line == 2
    assert out[0].from_line == 1

def test_detect_moves_duplicate_removals_match_first():
    # duplicate removals, expect to match to first removal based on line number
    input = [Removal (1, "test"), Addition(2, "test"), Removal (3, "test")]
    out = detect_moves(input)
    assert len(out) == 2
    # The move should be from line 1 to line 2
    assert isinstance(out[0], Move)
    assert out[0].content == "test"
    assert out[0].to_line == 2 # line_number for Move is its to_line
    assert out[0].from_line == 1
    # The second removal should remain a removal
    assert isinstance(out[1], Removal)
    assert out[1].content == "test"
    assert out[1].line_number == 3


# --- New Test Cases ---

def test_detect_moves_no_moves_only_additions():
    """No removals to pair with additions, so all remain additions."""
    input = [Addition(1, "line A"), Addition(2, "line B")]
    out = detect_moves(input)
    assert len(out) == 2
    assert isinstance(out[0], Addition) and out[0].content == "line A" and out[0].line_number == 1
    assert isinstance(out[1], Addition) and out[1].content == "line B" and out[1].line_number == 2

def test_detect_moves_no_moves_only_removals():
    """No additions to pair with removals, so all remain removals."""
    input = [Removal(1, "line A"), Removal(2, "line B")]
    out = detect_moves(input)
    assert len(out) == 2
    assert isinstance(out[0], Removal) and out[0].content == "line A" and out[0].line_number == 1
    assert isinstance(out[1], Removal) and out[1].content == "line B" and out[1].line_number == 2

def test_detect_moves_no_moves_mismatched_content():
    """Additions and removals with different content should not form moves."""
    input = [Removal(1, "line A"), Addition(2, "line B")]
    out = detect_moves(input)
    assert len(out) == 2
    assert isinstance(out[0], Removal) and out[0].content == "line A" and out[0].line_number == 1
    assert isinstance(out[1], Addition) and out[1].content == "line B" and out[1].line_number == 2

def test_detect_moves_multiple_distinct_moves():
    """Detects multiple independent move operations."""
    input = [
        Removal(1, "line A"),
        Addition(3, "line A"),  # Move 1->3
        Removal(2, "line B"),
        Addition(4, "line B")   # Move 2->4
    ]
    out = detect_moves(input)
    assert len(out) == 2
    # Ensure both moves are found, order by to_line (which is line_number for Move)
    assert isinstance(out[0], Move)
    assert out[0].content == "line A"
    assert out[0].from_line == 1
    assert out[0].to_line == 3

    assert isinstance(out[1], Move)
    assert out[1].content == "line B"
    assert out[1].from_line == 2
    assert out[1].to_line == 4

def test_detect_moves_intervening_changes():
    """A move should still be detected even with other changes in between."""
    input = [
        Removal(1, "line A"),
        Addition(2, "new line"),  # Intervening addition
        Removal(3, "old line"),    # Intervening removal
        Addition(4, "line A")     # Move 1->4
    ]
    out = detect_moves(input)
    assert len(out) == 3  # One move, one addition, one removal
    # Order by line_number (to_line for moves)
    assert isinstance(out[0], Addition) and out[0].content == "new line" and out[0].line_number == 2
    assert isinstance(out[1], Removal) and out[1].content == "old line" and out[1].line_number == 3
    assert isinstance(out[2], Move) and out[2].content == "line A" and out[2].from_line == 1 and out[2].to_line == 4

def test_detect_moves_content_change_not_a_move():
    """If content changes, it's a removal and an addition, not a move."""
    input = [Removal(1, "original content"), Addition(2, "modified content")]
    out = detect_moves(input)
    assert len(out) == 2
    assert isinstance(out[0], Removal) and out[0].content == "original content" and out[0].line_number == 1
    assert isinstance(out[1], Addition) and out[1].content == "modified content" and out[1].line_number == 2

def test_detect_moves_same_line_add_remove_not_a_move():
    """An addition and removal on the same line number should not be considered a move."""
    input = [Removal(1, "old"), Addition(1, "new")]
    out = detect_moves(input)
    assert len(out) == 2
    # Order will be Removal then Addition if they have the same line_number because of stable sort
    assert isinstance(out[0], Removal) and out[0].content == "old" and out[0].line_number == 1
    assert isinstance(out[1], Addition) and out[1].content == "new" and out[1].line_number == 1

def test_detect_moves_multiple_removals_one_addition_match_first_by_line():
    """
    If multiple removals match one addition, the one with the lowest line number
    (appearing first) should be matched as a move. The others remain removals.
    """
    input = [
        Removal(1, "test"),          # Should become a move from here
        Removal(2, "another line"),
        Removal(3, "test"),          # Should remain a removal
        Addition(4, "test")          # This addition
    ]
    out = detect_moves(input)
    assert len(out) == 3 # One move, two removals
    # Sorted by line_number (to_line for move)
    assert isinstance(out[0], Removal) and out[0].content == "another line" and out[0].line_number == 2
    assert isinstance(out[1], Removal) and out[1].content == "test" and out[1].line_number == 3
    assert isinstance(out[2], Move) and out[2].content == "test" and out[2].from_line == 1 and out[2].to_line == 4

def test_detect_moves_multiple_additions_one_removal_match_first_by_line():
    """
    If one removal matches multiple additions, only one addition should form a move.
    The other additions of the same content should remain additions.
    The assumption here is that the first encountered addition (by line number)
    that matches a removal will form the move.
    """
    input = [
        Removal(1, "test"),
        Addition(2, "test"), # This should become a move (1->2)
        Addition(3, "test")  # This should remain an addition
    ]
    out = detect_moves(input)
    assert len(out) == 2 # One move, one addition
    # Sorted by line_number (to_line for move)
    assert isinstance(out[0], Move) and out[0].content == "test" and out[0].from_line == 1 and out[0].to_line == 2
    assert isinstance(out[1], Addition) and out[1].content == "test" and out[1].line_number == 3

def test_detect_moves_empty_input():
    """Handling an empty list of changes."""
    input = []
    out = detect_moves(input)
    assert out == []

def test_detect_moves_complex_interleaved_operations():
    """A more complex mix of additions, removals, and moves."""
    input = [
        Removal(1, "line A"),
        Addition(2, "new line 1"),
        Removal(3, "line B"),
        Addition(4, "new line 2"),
        Addition(5, "line A"),  # Move from 1 -> 5
        Removal(6, "line C"),
        Addition(7, "line B"),  # Move from 3 -> 7
    ]
    out = detect_moves(input)
    assert len(out) == 5 # Two moves, two additions, one removal

    # Expected order based on line_number (to_line for moves)
    assert isinstance(out[0], Addition) and out[0].content == "new line 1" and out[0].line_number == 2
    assert isinstance(out[1], Addition) and out[1].content == "new line 2" and out[1].line_number == 4
    assert isinstance(out[2], Move) and out[2].content == "line A" and out[2].from_line == 1 and out[2].to_line == 5
    assert isinstance(out[3], Removal) and out[3].content == "line C" and out[3].line_number == 6
    assert isinstance(out[4], Move) and out[4].content == "line B" and out[4].from_line == 3 and out[4].to_line == 7


def test_detect_moves_unmatched_removal():
    """A removal without a corresponding addition should remain a removal."""
    input = [
        Removal(1, "line A"),  # No matching addition
        Addition(2, "line B")
    ]
    out = detect_moves(input)
    assert len(out) == 2
    assert isinstance(out[0], Removal) and out[0].content == "line A" and out[0].line_number == 1
    assert isinstance(out[1], Addition) and out[1].content == "line B" and out[1].line_number == 2

def test_detect_moves_unmatched_addition():
    """An addition without a corresponding removal should remain an addition."""
    input = [
        Addition(1, "line A"),  # No matching removal
        Removal(2, "line B")
    ]
    out = detect_moves(input)
    assert len(out) == 2
    assert isinstance(out[0], Addition) and out[0].content == "line A" and out[0].line_number == 1
    assert isinstance(out[1], Removal) and out[1].content == "line B" and out[1].line_number == 2