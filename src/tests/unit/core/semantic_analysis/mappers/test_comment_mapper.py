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

from textwrap import dedent

import pytest

from codestory.core.file_parser.file_parser import FileParser
from codestory.core.semantic_analysis.mappers.comment_mapper import CommentMapper
from codestory.core.semantic_analysis.mappers.query_manager import QueryManager

# -------------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------------


@pytest.fixture(scope="module")
def tools():
    """Initializes the heavy components once per module to speed up tests.

    Returns a tuple of (FileParser, CommentMapper).
    """
    qm = QueryManager.get_instance()
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
            {0, 1, 3, 4, 5, 6},
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
            {0, 2, 3},
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
            {0, 3},
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
            {0, 2, 3, 4},
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
            {0, 2, 3},
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
            {0, 1, 3},
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
            {0, 2, 4},
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
            {0, 1, 4},
        ),
        # --- RUBY ---
        (
            "ruby",
            "test.rb",
            """
            # 0: Pure comment
            x = 1 # 1: Inline
            =begin
            3: Block comment start
            4: Block comment content
            =end
            class Foo
            end
            """,
            {0, 2, 3, 4, 5},
        ),
        # --- PHP ---
        (
            "php",
            "test.php",
            """
            <?php
            // 1: Pure comment
            $x = 1; // 2: Inline
            /* 3: Block
               4: Block */
            function foo() {}
            ?>
            """,
            {1, 3, 4},
        ),
        # --- SWIFT ---
        (
            "swift",
            "test.swift",
            """
            // 0: Pure comment
            let x = 1 // 1: Inline
            /* 2: Block
               3: Block */
            func foo() {}
            """,
            {0, 2, 3},
        ),
        # --- KOTLIN ---
        (
            "kotlin",
            "Test.kt",
            """
            // 0: Pure comment
            val x = 1 // 1: Inline
            /* 2: Block
               3: Block */
            fun main() {}
            """,
            {0, 2, 3},
        ),
        # --- SCALA ---
        (
            "scala",
            "Test.scala",
            """
            // 0: Pure comment
            val x = 1 // 1: Inline
            /* 2: Block
               3: Block */
            def main(): Unit = {}
            """,
            {0, 2, 3},
        ),
        # --- R ---
        (
            "r",
            "test.R",
            """
            # 0: Pure comment
            x <- 1 # 1: Inline
            # 2: Another comment
            foo <- function() {
              # 4: Inside function
            }
            """,
            {0, 2, 4},
        ),
        # --- LUA ---
        (
            "lua",
            "test.lua",
            """
            -- 0: Pure comment
            x = 1 -- 1: Inline
            --[[ 2: Block start
                 3: Block content ]]
            function foo() end
            """,
            {0, 2, 3},
        ),
        # --- DART ---
        (
            "dart",
            "test.dart",
            """
            // 0: Pure comment
            /// 1: Doc comment
            int x = 1; // 2: Inline
            /* 3: Block */
            void main() {}
            """,
            {0, 1, 3},
        ),
        # --- ELIXIR ---
        (
            "elixir",
            "test.ex",
            """
            # 0: Pure comment
            x = 1 # 1: Inline
            # 2: Another comment
            defmodule Foo do
              # 4: Inside module
            end
            """,
            {0, 2, 4},
        ),
        # --- HASKELL ---
        (
            "haskell",
            "Test.hs",
            """
            -- 0: Pure comment
            x = 1 -- 1: Inline
            {- 2: Block start
               3: Block end -}
            main = return ()
            """,
            {0, 2, 3},
        ),
        # --- ERLANG ---
        (
            "erlang",
            "test.erl",
            """
            % 0: Pure comment
            -module(test). % 1: Inline
            % 2: Another comment
            foo() -> ok.
            """,
            {0, 2},
        ),
        # --- CLOJURE ---
        (
            "clojure",
            "test.clj",
            """
            ; 0: Pure comment
            (def x 1) ; 1: Inline
            ; 2: Another comment
            (defn foo [] nil)
            """,
            {0, 2},
        ),
        # --- SOLIDITY ---
        (
            "solidity",
            "Test.sol",
            """
            // 0: Pure comment
            /// 1: NatSpec comment
            contract Test {
                uint x = 1; // 3: Inline
                /* 4: Block */
            }
            """,
            {0, 1, 4},
        ),
        # --- JULIA ---
        (
            "julia",
            "test.jl",
            """
            # 0: Pure comment
            x = 1 # 1: Inline
            #= 2: Block start
               3: Block content =#
            function foo() end
            """,
            {0, 2, 3},
        ),
    ],
)
def test_pure_comment_identification(
    tools, language, filename, content, expected_lines
):
    parser, mapper = tools

    # Clean up the multiline string indentation
    clean_content = dedent(content).strip()

    # Adjust expected lines because .strip() removes the initial empty newline
    # from the multiline string definition.
    # We parse the cleaned content.

    parsed = parser.parse_file(
        filename.encode("utf-8"),
        clean_content.encode("utf-8"),
        [(0, len(clean_content.splitlines()) - 1)],
    )

    assert parsed is not None, f"tree-sitter failed to parse {language} content."
    assert parsed.detected_language == language

    cmap = mapper.build_comment_map(
        parsed.detected_language,
        parsed.root_node,
        parsed.content_bytes,
        parsed.line_ranges,
    )

    # Use set comparison for clear pytest diffs
    assert cmap.pure_comment_lines == expected_lines
