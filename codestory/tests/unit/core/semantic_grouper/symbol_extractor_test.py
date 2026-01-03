# -----------------------------------------------------------------------------
# dslate - Dual Licensed Software
# Copyright (c) 2025 Adem Can
#
# This file is part of DSLATE.
#
# DSLATE is available under a dual-license:
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


import pytest
from unittest.mock import Mock, patch
from codestory.core.semantic_grouper.symbol_extractor import SymbolExtractor
from codestory.core.semantic_grouper.query_manager import QueryManager

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


@patch("dslate.core.semantic_grouper.symbol_extractor.QueryManager")
def test_extract_defined_symbols(MockQueryManager):
    # Setup QueryManager mock
    qm = MockQueryManager.return_value

    # Mock run_query return value
    # Format: {match_class: [node1, node2]}
    node1 = Mock()
    node1.text = b"MyClass"

    node2 = Mock()
    node2.text = b"my_function"

    qm.run_query.return_value = {"class": [node1], "function": [node2]}

    # Mock create_qualified_symbol static method (it's called on the class)
    # Since we patched QueryManager class, we can configure the static method on the mock class
    def create_qualified_symbol_side_effect(match_class, text):
        return f"{match_class}:{text}"

    MockQueryManager.create_qualified_symbol.side_effect = (
        create_qualified_symbol_side_effect
    )

    extractor = SymbolExtractor(qm)

    symbols = extractor.extract_defined_symbols("python", Mock(), [])

    assert len(symbols) == 2
    assert "class:MyClass" in symbols
    assert "function:my_function" in symbols

    # Verify run_query call
    qm.run_query.assert_called_once()
    args, kwargs = qm.run_query.call_args
    assert args[0] == "python"
    assert kwargs["query_type"] == "token_definition"


@patch("dslate.core.semantic_grouper.symbol_extractor.QueryManager")
def test_extract_defined_symbols_empty(MockQueryManager):
    qm = MockQueryManager.return_value
    qm.run_query.return_value = {}

    extractor = SymbolExtractor(qm)
    symbols = extractor.extract_defined_symbols("python", Mock(), [])

    assert symbols == set()
