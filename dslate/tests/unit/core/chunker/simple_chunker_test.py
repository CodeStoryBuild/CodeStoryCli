import pytest
from unittest.mock import Mock
from dslate.core.chunker.simple_chunker import SimpleChunker

def test_simple_chunker_pass_through():
    """Test that SimpleChunker returns the input list as is."""
    chunker = SimpleChunker()
    chunks = [Mock(), Mock(), Mock()]
    context_manager = Mock()
    
    result = chunker.chunk(chunks, context_manager)
    
    assert result == chunks
    assert len(result) == 3
    assert result[0] is chunks[0]
