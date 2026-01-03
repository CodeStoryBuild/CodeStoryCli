import pytest
from textwrap import dedent

from codestory.core.file_reader.file_parser import FileParser
from codestory.core.semantic_grouper.comment_mapper import CommentMapper
from codestory.core.semantic_grouper.query_manager import QueryManager

# -------------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tools():
    """
    Initializes the heavy components once per module to speed up tests.
    Returns a tuple of (FileParser, CommentMapper).
    """
    qm = QueryManager()
    mapper = CommentMapper(qm)
    parser = FileParser()
    return parser, mapper

# -------------------------------------------------------------------------
# Parameterized Tests
# -------------------------------------------------------------------------

@pytest.mark.parametrize(
    "language, filename, content, expected_lines",
    [
        # --- PYTHON (Verifies the Docstring Fix) ---
        (
            "python",
            "test.py",
            """
            # 0: Pure comment
            x = 1  # 1: Inline (Code)
            def foo():
                \"\"\"
                4: Docstring start
                5: Docstring content
                \"\"\"
                pass
            """,
            {0, 1, 3, 4, 5, 6} 
        ),

        # --- JAVASCRIPT ---
        (
            "javascript",
            "test.js",
            """
            // 0: Pure
            const x = 1; // 1: Inline
            /* 2: Block Start
               3: Block End */
            function f() {}
            """,
            {0, 2, 3}
        ),

        # --- TYPESCRIPT ---
        (
            "typescript",
            "test.ts",
            """
            // 0: TS Comment
            interface User { // 1: Inline
                name: string;
                // 3: Pure inside
            }
            """,
            {0, 3}
        ),

        # --- JAVA ---
        (
            "java",
            "Test.java",
            """
            // 0: Pure
            public class Test {
                /**
                 * 2: Javadoc
                 */
                int x = 1; // 4: Inline
            }
            """,
            {0, 2, 3, 4}
        ),

        # --- C++ ---
        (
            "cpp",
            "test.cpp",
            """
            // 0: C++ Comment
            #include <iostream>
            /* 2: Block
               3: Block */
            int main() { return 0; }
            """,
            {0, 2, 3}
        ),

        # --- C# ---
        (
            "csharp",
            "Test.cs",
            """
            // 0: Regular
            /// 1: XML Doc
            namespace Demo {
                /* 3: Block */
                public class C {}
            }
            """,
            {0, 1, 3}
        ),

        # --- GO ---
        (
            "go",
            "main.go",
            """
            // 0: Go comment
            package main
            // 2: Pure
            func main() {
               /* 4: Block */
            }
            """,
            {0, 2, 4}
        ),

        # --- RUST ---
        (
            "rust",
            "main.rs",
            """
            // 0: Normal
            /// 1: Doc comment
            fn main() {
                let x = 5; // 3: Inline
                /* 4: Block */
            }
            """,
            {0, 1, 4}
        ),
    ],
)
def test_pure_comment_identification(tools, language, filename, content, expected_lines):
    parser, mapper = tools
    
    # Clean up the multiline string indentation
    clean_content = dedent(content).strip()
    
    # Adjust expected lines because .strip() removes the initial empty newline 
    # from the multiline string definition.
    # We parse the cleaned content.
    
    parsed = parser.parse_file(
        filename, 
        clean_content, 
        [(0, len(clean_content.splitlines()) - 1)]
    )
    
    assert parsed is not None, f"Tree-sitter failed to parse {language} content."
    assert parsed.detected_language == language

    cmap = mapper.build_comment_map(
        parsed.detected_language,
        parsed.root_node,
        parsed.content_bytes,
        parsed.line_ranges,
    )

    # Use set comparison for clear pytest diffs
    assert cmap.pure_comment_lines == expected_lines