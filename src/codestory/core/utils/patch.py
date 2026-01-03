def truncate_patch(
    patch: str | bytes,
    max_length: int = 200,
    truncate_line: str = "[TRUNCATED: remaining patch omitted]",
) -> str:
    """Truncates a patch string to a maximum length, adding ellipsis if necessary."""
    if len(patch) <= max_length:
        return patch

    lines = patch.splitlines()
    sum_length = 0
    i = 0

    while sum_length < (max_length - len(truncate_line)) and i < len(lines):
        sum_length += len(lines[i]) + 1  # +1 for the newline character
        i += 1

    return "\n".join(lines[:i] + [truncate_line]) if i < len(lines) else patch


def truncate_patch_bytes(
    patch: bytes,
    max_length: int = 200,
    truncate_line: bytes = b"[TRUNCATED: remaining patch omitted]",
) -> bytes:
    """Truncates a patch string to a maximum length, adding ellipsis if necessary."""
    if len(patch) <= max_length:
        return patch

    lines = patch.splitlines()
    sum_length = 0
    i = 0

    while sum_length < (max_length - len(truncate_line)) and i < len(lines):
        sum_length += len(lines[i]) + 1  # +1 for the newline character
        i += 1

    return b"\n".join(lines[:i] + [truncate_line]) if i < len(lines) else patch
