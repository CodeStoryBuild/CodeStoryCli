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


import pytest
from unittest.mock import Mock, patch
from codestory.core.file_reader.file_parser import FileParser, ParsedFile

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


@patch("codestory.core.file_reader.file_parser.get_lexer_for_filename")
def test_detect_language_success(mock_get_lexer):
    mock_lexer = Mock()
    mock_lexer.name = "Python"
    mock_get_lexer.return_value = mock_lexer

    lang = FileParser._detect_language("test.py", "content")
    assert lang == "python"


@patch("codestory.core.file_reader.file_parser.get_lexer_for_filename")
def test_detect_language_unknown(mock_get_lexer):
    # Simulate ClassNotFound from pygments
    from pygments.util import ClassNotFound

    mock_get_lexer.side_effect = ClassNotFound

    lang = FileParser._detect_language("unknown.xyz", "content")
    assert lang is None


@patch("codestory.core.file_reader.file_parser.get_parser")
@patch("codestory.core.file_reader.file_parser.FileParser._detect_language")
def test_parse_file_success(mock_detect, mock_get_parser):
    mock_detect.return_value = "python"

    mock_parser = Mock()
    mock_tree = Mock()
    mock_root = Mock()
    mock_tree.root_node = mock_root
    mock_parser.parse.return_value = mock_tree
    mock_get_parser.return_value = mock_parser

    result = FileParser.parse_file("test.py", "print('hello')", [])

    assert isinstance(result, ParsedFile)
    assert result.detected_language == "python"
    assert result.root_node == mock_root
    assert result.content_bytes == b"print('hello')"


@patch("codestory.core.file_reader.file_parser.FileParser._detect_language")
def test_parse_file_no_language(mock_detect):
    mock_detect.return_value = None

    result = FileParser.parse_file("test.txt", "content", [])
    assert result is None


@patch("codestory.core.file_reader.file_parser.get_parser")
@patch("codestory.core.file_reader.file_parser.FileParser._detect_language")
def test_parse_file_parser_error(mock_detect, mock_get_parser):
    mock_detect.return_value = "python"
    mock_get_parser.side_effect = Exception("Parser error")

    result = FileParser.parse_file("test.py", "content", [])
    assert result is None


@patch("codestory.core.file_reader.file_parser.get_parser")
@patch("codestory.core.file_reader.file_parser.FileParser._detect_language")
def test_parse_file_parsing_exception(mock_detect, mock_get_parser):
    mock_detect.return_value = "python"
    mock_parser = Mock()
    mock_parser.parse.side_effect = Exception("Parsing failed")
    mock_get_parser.return_value = mock_parser

    result = FileParser.parse_file("test.py", "content", [])
    assert result is None


def test_map_lexer_to_language():
    # Direct mapping
    assert FileParser._map_lexer_to_language("Python") == "python"
    assert FileParser._map_lexer_to_language("JavaScript") == "javascript"

    # Variations
    assert FileParser._map_lexer_to_language("C++") == "cpp"
    assert FileParser._map_lexer_to_language("cxx") == "cpp"
    assert FileParser._map_lexer_to_language("TS") == "typescript"

    # Unknown
    assert FileParser._map_lexer_to_language("UnknownLang") is None
