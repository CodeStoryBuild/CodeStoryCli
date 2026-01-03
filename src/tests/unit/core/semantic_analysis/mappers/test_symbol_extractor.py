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

from unittest.mock import Mock, patch

from codestory.core.semantic_analysis.mappers.symbol_extractor import SymbolExtractor

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


@patch("codestory.core.semantic_analysis.mappers.symbol_extractor.QueryManager")
def test_extract_defined_symbols(MockQueryManager):
    # Setup QueryManager mock
    qm = MockQueryManager.return_value

    # Mock run_query return value
    # Format: {match_class: [node1, node2]}
    node1 = Mock()
    node1.text = b"MyClass"

    node2 = Mock()
    node2.text = b"my_function"

    qm.run_query_captures.return_value = {"class": [node1], "function": [node2]}

    # Mock create_qualified_symbol static method (it's called on the class)
    # Since we patched QueryManager class, we can configure the static method on the mock class
    def create_qualified_symbol_side_effect(match_class, text, file_name):
        return f"{text} {match_class} {file_name}"

    MockQueryManager.create_qualified_symbol.side_effect = (
        create_qualified_symbol_side_effect
    )

    extractor = SymbolExtractor(qm)

    symbols = extractor.extract_defined_symbols("python", Mock(), [])

    assert len(symbols) == 2
    assert "MyClass class python" in symbols
    assert "my_function function python" in symbols

    # Verify run_query call
    qm.run_query_captures.assert_called_once()
    args, kwargs = qm.run_query_captures.call_args
    assert args[0] == "python"
    assert kwargs["query_type"] == "token_definition"


@patch("codestory.core.semantic_analysis.mappers.symbol_extractor.QueryManager")
def test_extract_defined_symbols_empty(MockQueryManager):
    qm = MockQueryManager.return_value
    qm.run_query_captures.return_value = {}

    extractor = SymbolExtractor(qm)
    symbols = extractor.extract_defined_symbols("python", Mock(), [])

    assert symbols == set()
