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

from codestory.core.file_parser.file_parser import FileParser, ParsedFile

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


@patch("codestory.core.file_parser.file_parser.get_parser")
@patch("codestory.core.file_parser.file_parser.FileParser._detect_language")
def test_parse_file_success(mock_detect, mock_get_parser):
    mock_detect.return_value = "python"

    mock_parser = Mock()
    mock_tree = Mock()
    mock_root = Mock()
    mock_tree.root_node = mock_root
    mock_parser.parse.return_value = mock_tree
    mock_get_parser.return_value = mock_parser

    result = FileParser.parse_file(b"test.py", b"print('hello')", [])

    assert isinstance(result, ParsedFile)
    assert result.detected_language == "python"
    assert result.root_node == mock_root
    assert result.content_bytes == b"print('hello')"


@patch("codestory.core.file_parser.file_parser.FileParser._detect_language")
def test_parse_file_no_language(mock_detect):
    mock_detect.return_value = None

    result = FileParser.parse_file(b"test.txt", b"content", [])
    assert result is None


@patch("codestory.core.file_parser.file_parser.get_parser")
@patch("codestory.core.file_parser.file_parser.FileParser._detect_language")
def test_parse_file_parser_error(mock_detect, mock_get_parser):
    mock_detect.return_value = "python"
    mock_get_parser.side_effect = Exception("Parser error")

    result = FileParser.parse_file(b"test.py", b"content", [])
    assert result is None


@patch("codestory.core.file_parser.file_parser.get_parser")
@patch("codestory.core.file_parser.file_parser.FileParser._detect_language")
def test_parse_file_parsing_exception(mock_detect, mock_get_parser):
    mock_detect.return_value = "python"
    mock_parser = Mock()
    mock_parser.parse.side_effect = Exception("Parsing failed")
    mock_get_parser.return_value = mock_parser

    result = FileParser.parse_file(b"test.py", b"content", [])
    assert result is None
