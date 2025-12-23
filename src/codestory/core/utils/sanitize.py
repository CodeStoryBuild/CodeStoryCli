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
    """
    Sanitizes text output from LLMs by removing problematic characters.

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
