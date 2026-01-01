# -----------------------------------------------------------------------------
# /*
#  * Copyright (C) 2025 CodeStory
#  *
#  * This program is free software; you can redistribute it and/or modify
#  * it under the terms of the GNU General Public License as published by
#  * the Free Software Foundation; Version 2.
#  *
#  * This program is distributed in the hope that it will be useful,
#  * but WITHOUT ANY WARRANTY; without even the implied warranty of
#  * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  * GNU General Public License for more details.
#  *
#  * You should have received a copy of the GNU General Public License
#  * along with this program; if not, you can contact us at support@codestory.build
#  */
# -----------------------------------------------------------------------------

"""Utilities for sanitizing LLM outputs."""


def sanitize_llm_text(text: str) -> str:
    """Sanitizes text output from LLMs by removing problematic characters.

    LLMs occasionally produce control characters like null bytes (\x00) which
    cause failures in downstream processing, particularly on Windows where
    subprocess.CreateProcess cannot handle null characters in arguments.

    Args:
        text: Raw text from LLM output.

    Returns:
        Sanitized text with problematic characters removed.
    """
    if not text:
        return text

    # Remove null bytes - these break Windows subprocess calls
    result = text.replace("\x00", "")

    # Strip leading/trailing whitespace that LLMs often include
    result = result.strip()

    return result


def truncate_patch(
    patch: str,
    max_length: int = 200,
    truncate_line: str = "[TRUNCATED: remaining patch omitted]",
) -> str:
    """Truncates a patch string to a maximum length."""
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
