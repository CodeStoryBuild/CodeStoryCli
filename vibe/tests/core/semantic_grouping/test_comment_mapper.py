from pathlib import Path
from importlib.resources import files

from vibe.core.file_reader.file_parser import FileParser
from vibe.core.semantic_grouper.comment_mapper import CommentMapper
from vibe.core.semantic_grouper.query_manager import QueryManager


def test_pure_comment_lines_python():
    # Arrange: sample Python content with various comment patterns
    content = "\n".join(
        [
            "# top-level comment",          # 0: pure comment
            "x = 1  # inline comment",      # 1: not pure
            "   # indented comment",        # 2: pure comment
            "",                              # 3: empty -> not counted
            "def f(): pass",                # 4: code
            "    # inside function",        # 5: pure comment
            "    pass  # trailing",         # 6: not pure
            "# multi 1",                    # 7: pure comment
            "# multi 2",                    # 8: pure comment
            "\"\"\"",                    # 9: pure comment
            "# multi 2",                    # 10: pure comment (double match)
            "\"\"\"",                    # 11: pure comment
        ]
    )

    parser = FileParser()
    parsed = parser.parse_file("test.py", content, [(0, len(content.splitlines()) - 1)])
    assert parsed is not None

    # QueryManager expects a path-like with .open(); point at packaged language_config
    lang_cfg_path = files("vibe") / "resources" / "language_config.json"

    q = QueryManager(lang_cfg_path)
    mapper = CommentMapper(q)

    cmap = mapper.build_comment_map(
        parsed.detected_language,
        parsed.root_node,
        parsed.content_bytes,
        parsed.line_ranges,
    )

    # Assert: only lines that have nothing but comments (ignoring whitespace) are included
    assert 0 in cmap.pure_comment_lines
    assert 1 not in cmap.pure_comment_lines
    assert 2 in cmap.pure_comment_lines
    assert 3 not in cmap.pure_comment_lines
    assert 4 not in cmap.pure_comment_lines
    assert 5 in cmap.pure_comment_lines
    assert 6 not in cmap.pure_comment_lines
    assert 7 in cmap.pure_comment_lines
    assert 8 in cmap.pure_comment_lines
    assert 9 in cmap.pure_comment_lines
    assert 10 in cmap.pure_comment_lines
    assert 11 in cmap.pure_comment_lines
