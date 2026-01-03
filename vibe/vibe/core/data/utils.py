from typing import List, Union
from .models import Addition, Removal, Move, Replacement


def detect_moves(
    parsed_content: List[Union[Addition, Removal]],
) -> List[Union[Addition, Removal, Move]]:
    # Map to store removals by content. The value will be a list of line numbers
    # associated with that content, allowing us to pick the lowest.
    removal_map = {}

    out: List[Union[Addition, Removal, Move]] = parsed_content.copy()

    for i, item in enumerate(out):
        if isinstance(item, Removal):
            removal_map.setdefault(item.content, []).append((item.line_number, i))

    removals = []

    additions = []

    for i, item in enumerate(out):
        if isinstance(item, Addition):
            # If there's a matching removal and it hasn't been used yet
            if item.content in removal_map and removal_map[item.content]:
                from_line, from_idx = removal_map[item.content].pop(
                    0
                )  # Get and remove the lowest line number

                # since a match was found, remove this addition and the associated removal from the list
                removals.append(from_idx)
                removals.append(i)

                # add a new move object
                additions.append(
                    Move(
                        content=item.content,
                        from_line=from_line,
                        to_line=item.line_number,
                    )
                )

    for rem in sorted(removals, reverse=True):
        del out[rem]

    for add in additions:
        out.append(add)

    return sorted(out, key=lambda x: x.line_number)


def detect_replacements(
    content: List[Union[Addition, Removal, Move]],
) -> List[Union[Addition, Removal, Move, Replacement]]:
    clarified: List[Union[Addition, Removal, Move, Replacement]] = []
    i = 0
    while i < len(content):
        curr = content[i]
        nxt = content[i + 1] if i + 1 < len(content) else None

        if isinstance(curr, Removal) and isinstance(nxt, Addition):
            if curr.line_number == nxt.line_number:
                # Replacement detected
                clarified.append(
                    Replacement(
                        old_content=curr.content,
                        new_content=nxt.content,
                        line_number=curr.line_number,
                    )
                )
                i += 2  # skip the next one
                continue

        # Otherwise keep the item as-is
        clarified.append(curr)
        i += 1

    return clarified


def format_content_json(parsed_content) -> str:
    """
    Converts a list of structured diff objects into a standardized JSON format
    optimized for LLM comprehension.

    Args:
        file_path: The path of the file being modified.
        change_list: The list of Addition, Removal, Move, or Replacement objects.

    Returns:
        A JSON string representing the structured diff.
    """
    w_moves = detect_moves(parsed_content)
    simplified_diff = detect_replacements(w_moves)

    structured_changes = []

    for change in simplified_diff:
        change_dict = {}

        if isinstance(change, Addition):
            change_dict = {
                "type": "Addition",
                "line_number": change.line_number,
                "content": change.content,
            }

        elif isinstance(change, Removal):
            change_dict = {
                "type": "Removal",
                "line_number": change.line_number,  # Line number in the old file state
                "content": change.content,
            }

        elif isinstance(change, Move):
            change_dict = {
                "type": "Move",
                "from_line": change.from_line,
                "to_line": change.to_line,
                "content": change.content,
            }

        elif isinstance(change, Replacement):
            change_dict = {
                "type": "Replacement",
                "line_number": change.line_number,
                "old_content": change.old_content,
                "new_content": change.new_content,
            }

        else:
            # Skip or log unknown types
            continue

        structured_changes.append(change_dict)

    return structured_changes
