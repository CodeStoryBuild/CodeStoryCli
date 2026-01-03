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

from unittest.mock import Mock

from codestory.core.chunker.simple_chunker import SimpleChunker


def test_simple_chunker_pass_through():
    """Test that SimpleChunker returns the input list as is."""
    chunker = SimpleChunker()
    chunks = [Mock(), Mock(), Mock()]
    context_manager = Mock()

    result = chunker.chunk(chunks, context_manager)

    assert result == chunks
    assert len(result) == 3
    assert result[0] is chunks[0]
