# -----------------------------------------------------------------------------
# codestory - Dual Licensed Software
# Copyright (c) 2025 Adem Can
#
# This file is part of codestory.
#
# codestory is available under a dual-license:
#   1. AGPLv3 (Affero General Public License v3)
#      - See LICENSE.txt and LICENSE-AGPL.txt
#      - Online: https://www.gnu.org/licenses/agpl-3.0.html
#
#   2. Commercial License
#      - For proprietary or revenue-generating use,
#        including SaaS, embedding in closed-source software,
#        or avoiding AGPL obligations.
#      - See LICENSE.txt and COMMERCIAL-LICENSE.txt
#      - Contact: ademfcan@gmail.com
#
# By using this file, you agree to the terms of one of the two licenses above.
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
