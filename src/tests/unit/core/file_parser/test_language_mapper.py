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

import pytest

from codestory.core.file_parser.language_mapper import detect_tree_sitter_language

# -----------------------------------------------------------------------------
# 1. Simple Extension & Filename Tests
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename, expected_lang",
    [
        # Common Extensions
        ("test.py", "python"),
        ("script.js", "javascript"),
        ("styles.css", "css"),
        ("index.html", "html"),
        ("main.rs", "rust"),
        ("main.go", "go"),
        ("App.tsx", "tsx"),
        ("types.ts", "typescript"),
        ("script.php", "php"),
        ("config.yaml", "yaml"),
        ("data.json", "json"),
        # Specific Filenames
        ("Dockerfile", "dockerfile"),
        ("Makefile", "make"),
        ("makefile", "make"),  # Case insensitivity check
        ("CMakeLists.txt", "cmake"),
        ("go.mod", "gomod"),
        ("go.sum", "gosum"),
        ("Jenkinsfile", "groovy"),
        (".gitignore", "gitignore"),
        ("package.json", "json"),
        (".bashrc", "bash"),
        # Case Insensitivity on Extensions
        ("SCRIPT.PY", "python"),
        ("Index.HTML", "html"),
    ],
)
def test_simple_detections(filename, expected_lang):
    """Test standard extensions and specific filenames."""
    assert detect_tree_sitter_language(filename.encode("utf-8"), b"") == expected_lang


# -----------------------------------------------------------------------------
# 2. Ambiguity Resolution Tests
# -----------------------------------------------------------------------------


def test_ambiguous_h_file():
    """Test distinguishing between C and C++ header files."""
    c_content = b"#include <stdio.h>\nint main() { return 0; }"
    cpp_content = b"#include <iostream>\nclass MyClass { public: int x; };"

    assert detect_tree_sitter_language(b"header.h", c_content) == "c"
    assert detect_tree_sitter_language(b"header.h", cpp_content) == "cpp"
    # Default fallback
    assert detect_tree_sitter_language(b"header.h", b"") == "c"


def test_ambiguous_m_file():
    """Test distinguishing between Objective-C and Matlab files."""
    objc_content = b"#import <Foundation/Foundation.h>\n@interface MyClass : NSObject"
    matlab_content = b"% This is a comment\nfunction y = average(x)"

    assert detect_tree_sitter_language(b"class.m", objc_content) == "objc"
    assert detect_tree_sitter_language(b"calc.m", matlab_content) == "matlab"
    # Default fallback
    assert detect_tree_sitter_language(b"unknown.m", b"") == "objc"


def test_ambiguous_v_file():
    """Test distinguishing between Verilog and V files."""
    verilog_content = b"module adder(input a, output b); endmodule"
    v_content = b"fn main() { println('hello') }"

    assert detect_tree_sitter_language(b"chip.v", verilog_content) == "verilog"
    assert detect_tree_sitter_language(b"main.v", v_content) == "v"


# -----------------------------------------------------------------------------
# 3. Shebang Tests
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "shebang, expected_lang",
    [
        ("#!/bin/bash", "bash"),
        ("#!/bin/sh", "bash"),
        ("#!/usr/bin/env python3", "python"),
        ("#!/usr/bin/env python", "python"),
        ("#!/usr/bin/python3.9", "python"),
        ("#!/usr/bin/env node", "javascript"),
        ("#!/usr/bin/node", "javascript"),
        ("#!/usr/bin/perl", "perl"),
        ("#!/usr/bin/env ruby", "ruby"),
        ("#!/usr/bin/make -f", "make"),
    ],
)
def test_shebang_detection(shebang, expected_lang):
    """Test language detection via shebang line when extension is missing."""
    content = f"{shebang}\n# Some code here"
    # Using a filename with no extension to force shebang check
    assert (
        detect_tree_sitter_language(b"myscript", content.encode("utf-8"))
        == expected_lang
    )


# -----------------------------------------------------------------------------
# 4. Edge Cases & Paths
# -----------------------------------------------------------------------------


def test_paths_with_directories():
    """Ensure directory paths don't confuse the filename extractor."""
    assert detect_tree_sitter_language(b"src/components/Button.tsx") == "tsx"
    assert detect_tree_sitter_language(b"./deeply/nested/Makefile") == "make"


def test_unknown_extension():
    """Ensure unknown extensions return None."""
    assert detect_tree_sitter_language(b"file.xyz123") is None
    assert (
        detect_tree_sitter_language(b"README.txt") is None
    )  # assuming txt isn't mapped


def test_mixed_ambiguity_signals():
    """Test priority: filename > extension > content."""
    # Even if content looks like C++, if the extension is .c, it should be C
    # (The function strictly checks .h for ambiguity, but .c is hardmapped to c)
    content = b"class MyClass { };"
    assert detect_tree_sitter_language(b"file.c", content) == "c"
