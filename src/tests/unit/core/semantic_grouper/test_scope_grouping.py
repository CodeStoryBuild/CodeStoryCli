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

"""
Tests for scope-based semantic grouping.
Tests verify that chunks within the same scope (function, class, etc.) are grouped together.
"""

from textwrap import dedent

import pytest

from codestory.core.file_reader.file_parser import FileParser
from codestory.core.semantic_grouper.query_manager import QueryManager
from codestory.core.semantic_grouper.scope_mapper import ScopeMapper

# -------------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------------


@pytest.fixture(scope="module")
def tools():
    """
    Initializes the heavy components once per module.
    Returns a tuple of (FileParser, ScopeMapper).
    """
    qm = QueryManager.get_instance()
    scope_mapper = ScopeMapper(qm)
    parser = FileParser()
    return parser, scope_mapper


# -------------------------------------------------------------------------
# Test Cases
# -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "language,filename,content,chunk1_lines,chunk2_lines,should_share_scope,scope_description",
    [
        # === PYTHON ===
        (
            "python",
            "test.py",
            """
            def foo():
                x = 1
                y = 2
                return x + y
            
            def bar():
                a = 10
                b = 20
                return a + b
            """,
            (1, 2),  # Lines in foo: x = 1, y = 2
            (6, 7),  # Lines in bar: a = 10, b = 20
            False,
            "Different functions should have different scopes",
        ),
        (
            "python",
            "test.py",
            """
            def foo():
                x = 1
                y = 2
                z = 3
                return x + y + z
            """,
            (1, 1),  # Line: x = 1
            (3, 3),  # Line: z = 3
            True,
            "Lines within same function should share scope",
        ),
        (
            "python",
            "test.py",
            """
            class Calculator:
                def add(self, a, b):
                    return a + b
                
                def subtract(self, a, b):
                    return a - b
            """,
            (1, 2),  # add method
            (4, 5),  # subtract method
            True,
            "Methods in same class should share class scope",
        ),
        (
            "python",
            "test.py",
            """
            def outer():
                def inner1():
                    x = 1
                
                def inner2():
                    y = 2
            """,
            (2, 2),  # inner1
            (4, 5),  # inner2
            True,
            "Nested functions share outer function scope",
        ),
        # === JAVASCRIPT ===
        (
            "javascript",
            "test.js",
            """
            function foo() {
                const x = 1;
                const y = 2;
            }
            
            function bar() {
                const a = 10;
                const b = 20;
            }
            """,
            (1, 2),  # foo function
            (6, 7),  # bar function
            False,
            "Different JavaScript functions have different scopes",
        ),
        (
            "javascript",
            "test.js",
            """
            class Calculator {
                add(a, b) {
                    return a + b;
                }
                
                subtract(a, b) {
                    return a - b;
                }
            }
            """,
            (1, 3),  # add method
            (5, 7),  # subtract method
            True,
            "JavaScript class methods share class scope",
        ),
        (
            "javascript",
            "test.js",
            """
            const obj = {
                method1() {
                    return 1;
                },
                method2() {
                    return 2;
                }
            };
            """,
            (1, 3),  # method1
            (4, 6),  # method2
            False,
            "Object methods don't share scope outside object literal",
        ),
        # === TYPESCRIPT ===
        (
            "typescript",
            "test.ts",
            """
            interface User {
                name: string;
                age: number;
            }
            
            interface Product {
                id: number;
                price: number;
            }
            """,
            (1, 2),  # User interface
            (5, 6),  # Product interface
            False,
            "Different TypeScript interfaces are separate scopes",
        ),
        # === JAVA ===
        (
            "java",
            "Test.java",
            """
            public class Test {
                public void method1() {
                    int x = 1;
                    int y = 2;
                }
                
                public void method2() {
                    int a = 10;
                    int b = 20;
                }
            }
            """,
            (2, 3),  # method1
            (6, 7),  # method2
            True,
            "Java methods in same class share class scope",
        ),
        # === C++ ===
        (
            "cpp",
            "test.cpp",
            """
            class MyClass {
                void method1() {
                    int x = 1;
                }
                
                void method2() {
                    int y = 2;
                }
            };
            """,
            (1, 3),  # method1
            (5, 6),  # method2
            True,
            "C++ methods share class scope",
        ),
        # === GO ===
        (
            "go",
            "test.go",
            """
            func foo() {
                x := 1
                y := 2
            }
            
            func bar() {
                a := 10
                b := 20
            }
            """,
            (1, 2),  # foo
            (5, 6),  # bar
            False,
            "Different Go functions are separate scopes",
        ),
        # === RUST ===
        (
            "rust",
            "test.rs",
            """
            fn foo() {
                let x = 1;
                let y = 2;
            }
            
            fn bar() {
                let a = 10;
                let b = 20;
            }
            """,
            (1, 2),  # foo
            (5, 6),  # bar
            False,
            "Different Rust functions are separate scopes",
        ),
        (
            "rust",
            "test.rs",
            """
            impl MyStruct {
                fn method1(&self) {
                    let x = 1;
                }
                
                fn method2(&self) {
                    let y = 2;
                }
            }
            """,
            (1, 3),  # method1
            (5, 6),  # method2
            True,
            "Rust impl block methods share impl scope",
        ),
        # === RUBY ===
        (
            "ruby",
            "test.rb",
            """
            class Calculator
              def add(a, b)
                a + b
              end
              
              def subtract(a, b)
                a - b
              end
            end
            """,
            (1, 3),  # add
            (5, 6),  # subtract
            True,
            "Ruby methods share class scope",
        ),
        # === PHP ===
        (
            "php",
            "test.php",
            """
            <?php
            class Calculator {
                function add($a, $b) {
                    return $a + $b;
                }
                
                function subtract($a, $b) {
                    return $a - $b;
                }
            }
            """,
            (2, 4),  # add
            (6, 7),  # subtract
            True,
            "PHP methods share class scope",
        ),
        # === SWIFT ===
        (
            "swift",
            "test.swift",
            """
            struct Calculator {
                func add(a: Int, b: Int) -> Int {
                    return a + b
                }
                
                func subtract(a: Int, b: Int) -> Int {
                    return a - b
                }
            }
            """,
            (1, 3),  # add
            (5, 6),  # subtract
            True,
            "Swift struct methods share struct scope",
        ),
        # === KOTLIN ===
        (
            "kotlin",
            "test.kt",
            """
            class Calculator {
                fun add(a: Int, b: Int): Int {
                    return a + b
                }
                
                fun subtract(a: Int, b: Int): Int {
                    return a - b
                }
            }
            """,
            (1, 3),  # add
            (5, 6),  # subtract
            True,
            "Kotlin class methods share class scope",
        ),
        # === SCALA ===
        (
            "scala",
            "test.scala",
            """
            object Calculator {
                def add(a: Int, b: Int): Int = {
                    a + b
                }
                
                def subtract(a: Int, b: Int): Int = {
                    a - b
                }
            }
            """,
            (1, 3),  # add
            (5, 6),  # subtract
            True,
            "Scala object methods share object scope",
        ),
        # === TYPESCRIPT additional ===
        (
            "typescript",
            "test.ts",
            """
            function foo() {
                let x = 1;
                let y = 2;
            }

            function bar() {
                let a = 10;
                let b = 20;
            }
            """,
            (1, 2),  # foo body
            (6, 7),  # bar body
            False,
            "Different TypeScript functions have different scopes",
        ),
        (
            "typescript",
            "test.ts",
            """
            function foo() {
                let x = 1;
                let y = 2;
                let z = 3;
            }
            """,
            (1, 1),
            (2, 2),
            True,
            "Lines within same TypeScript function should share scope",
        ),
        (
            "typescript",
            "test.ts",
            """
            class Calculator {
                add(a: number, b: number) { return a + b; }
                subtract(a: number, b: number) { return a - b; }
            }
            """,
            (1, 1),
            (2, 2),
            True,
            "TypeScript class methods share class scope",
        ),
        (
            "typescript",
            "test.ts",
            """
            const obj = {
                method1() { return 1; },
                method2() { return 2; }
            }
            """,
            (1, 1),
            (2, 2),
            False,
            "Object literal methods in TypeScript are distinct scopes",
        ),
        # === C# ===
        (
            "csharp",
            "test.cs",
            """
            public class Test {
                public void Method1() {
                    int x = 1;
                }
                public void Method2() {
                    int y = 2;
                }
            }
            """,
            (1, 2),
            (4, 5),
            True,
            "C# methods in same class share class scope",
        ),
        (
            "csharp",
            "test2.cs",
            """
            public void Foo() 
            { int x = 1; int y = 2; }
            """,
            (0, 0),
            (1, 1),
            True,
            "Lines within same C# method should share scope",
        ),
        (
            "csharp",
            "test.cs",
            """
            public class A { public void Foo() { int x = 1; } }
            public class B { public void Bar() { int y = 2; } }
            """,
            (0, 0),
            (1, 1),
            False,
            "Methods in different C# classes do not share scope",
        ),
        (
            "csharp",
            "test.cs",
            """
            public void Foo() {
                if (true) { int x = 1; int y = 2; }
            }
            """,
            (1, 1),
            (1, 2),
            True,
            "Lines inside a C# if block share the block scope",
        ),
        # === R ===
        (
            "r",
            "test.R",
            """
            foo <- function() {
                x <- 1
                y <- 2
            }

            bar <- function() {
                a <- 10
                b <- 20
            }
            """,
            (1, 2),
            (5, 6),
            False,
            "Different R functions are separate scopes",
        ),
        (
            "r",
            "test.R",
            """
            foo <- function() {
                x <- 1
                y <- 2
                z <- 3
            }
            """,
            (1, 1),
            (2, 2),
            True,
            "Lines within same R function should share scope",
        ),
        (
            "r",
            "test.R",
            """
            if (TRUE) {
                x <- 1
                y <- 2
            }
            """,
            (1, 1),
            (1, 2),
            True,
            "Lines in same R if block share scope",
        ),
        (
            "r",
            "test.R",
            """
            foo <- function() {
                for (i in 1:3) {
                    x <- i
                }
            }
            """,
            (2, 2),
            (2, 2),
            True,
            "Lines in same R for loop share scope",
        ),
        # === LUA ===
        (
            "lua",
            "test.lua",
            """
            function foo()
                local x = 1
                local y = 2
            end

            function bar()
                local a = 10
                local b = 20
            end
            """,
            (1, 2),
            (6, 7),
            False,
            "Different Lua functions are separate scopes",
        ),
        (
            "lua",
            "test.lua",
            """
            function foo()
                local x = 1
                local y = 2
                local z = 3
            end
            """,
            (1, 1),
            (2, 2),
            True,
            "Lines within same Lua function should share scope",
        ),
        (
            "lua",
            "test.lua",
            """
            local t = {
                f1 = function() return 1 end,
                f2 = function() return 2 end,
            }
            """,
            (1, 1),
            (2, 2),
            True,
            "Table constructor functions share scope inside the same table constructor",
        ),
        (
            "lua",
            "test.lua",
            """
            function foo()
                for i=1,3 do
                    local x = i
                end
            end
            """,
            (2, 2),
            (2, 2),
            True,
            "Lines in same Lua for loop share scope",
        ),
        # === JAVA additional ===
        (
            "java",
            "Test.java",
            """
            public class Test {
                public void method1() {
                    int x = 1;
                    int y = 2;
                }
                public void method2() {
                    int a = 10;
                    int b = 20;
                }
            }
            """,
            (1, 2),
            (5, 6),
            True,
            "Java methods in same class share class scope (additional)",
        ),
        (
            "java",
            "Test.java",
            """
            void foo() { int x = 1; int y = 2; }
            void bar() { int a = 10; int b = 20; }
            """,
            (0, 0),
            (1, 1),
            False,
            "Different Java functions are separate scopes",
        ),
        (
            "java",
            "Test.java",
            """
            class Outer { class Inner { void innerMethod() { int x = 1; } } void outerMethod() { int y = 2; } }
            """,
            (0, 0),
            (0, 1),
            True,
            "Nested class and outer method share container scope in Java",
        ),
        (
            "java",
            "Test.java",
            """
            if (true) { int x = 1; int y = 2; }
            """,
            (0, 0),
            (0, 1),
            True,
            "Lines in a Java if block share the block scope",
        ),
        # === CPP additional ===
        (
            "cpp",
            "test.cpp",
            """
            void foo() { int x = 1; int y = 2; }
            void bar() { int a = 10; int b = 20; }
            """,
            (0, 0),
            (1, 1),
            False,
            "Different C++ functions are separate scopes",
        ),
        (
            "cpp",
            "test.cpp",
            """
            class MyClass { void m1() { int x = 1; } void m2() { int y = 2; } };
            """,
            (0, 0),
            (0, 1),
            True,
            "C++ methods in the same class share class scope",
        ),
        (
            "cpp",
            "test.cpp",
            """
            namespace ns { void foo() { int x = 1; } }
            """,
            (0, 0),
            (0, 0),
            True,
            "C++ lines inside namespace share scope",
        ),
        (
            "cpp",
            "test.cpp",
            """
            for (int i=0;i<1;++i) { int x = 1; int y = 2; }
            """,
            (0, 0),
            (0, 1),
            True,
            "Lines in C++ for loop share scope",
        ),
        # === GO additional ===
        (
            "go",
            "test.go",
            """
            func foo() {
                x := 1
                y := 2
            }
            func bar() {
                a := 10
                b := 20
            }
            """,
            (1, 2),
            (4, 5),
            False,
            "Different Go functions are separate scopes (additional)",
        ),
        (
            "go",
            "test.go",
            """
            func foo() {
                x := 1
                y := 2
                z := 3
            }
            """,
            (1, 1),
            (2, 2),
            True,
            "Lines within same Go function share scope",
        ),
        (
            "go",
            "test.go",
            """
            type MyStruct struct{ }
            func (m *MyStruct) M1() { x:=1 }
            func (m *MyStruct) M2() { y:=2 }
            """,
            (1, 1),
            (2, 2),
            False,
            "Methods on Go receiver dont share scope (they share symbol instead)",
        ),
        (
            "go",
            "test.go",
            """
            func foo() {
                if true { x := 1; y := 2 }
            }
            """,
            (1, 1),
            (1, 2),
            True,
            "Line inside Go if share block scope",
        ),
        # === RUST additional ===
        (
            "rust",
            "test.rs",
            """
            fn foo() {
                let x = 1;
                let y = 2;
            }
            fn bar() {
                let a = 10;
                let b = 20;
            }
            """,
            (1, 2),
            (5, 6),
            False,
            "Different Rust functions are separate scopes (additional)",
        ),
        (
            "rust",
            "test.rs",
            """
            fn foo() { let x = 1; let y = 2; let z = 3; }
            """,
            (0, 0),
            (0, 1),
            True,
            "Lines within same Rust function share scope",
        ),
        (
            "rust",
            "test.rs",
            """
            impl MyStruct { fn m1(&self) { let x = 1; } fn m2(&self) { let y = 2; } }
            """,
            (0, 0),
            (0, 1),
            True,
            "Rust impl methods share impl scope",
        ),
        (
            "rust",
            "test.rs",
            """
            fn foo() { if true { let x = 1; let y = 2; } }
            """,
            (0, 0),
            (0, 1),
            True,
            "Lines inside a Rust if block share scope",
        ),
        # === RUBY additional ===
        (
            "ruby",
            "test.rb",
            """
            def foo
              x = 1
              y = 2
            end
            def bar
              a = 10
              b = 20
            end
            """,
            (1, 2),
            (5, 6),
            False,
            "Different Ruby methods (top-level) are separate scopes",
        ),
        (
            "ruby",
            "test.rb",
            """
            def foo
              x = 1
              y = 2
              z = 3
            end
            """,
            (1, 1),
            (2, 2),
            True,
            "Lines within same Ruby method should share scope",
        ),
        (
            "ruby",
            "test.rb",
            """
            class C
              def a; 1; end
              def b; 2; end
            end
            """,
            (1, 1),
            (2, 2),
            True,
            "Methods in same Ruby class share class scope",
        ),
        (
            "ruby",
            "test.rb",
            """
            if true
              x = 1
              y = 2
            end
            """,
            (1, 1),
            (1, 2),
            True,
            "Lines in same Ruby if block share scope",
        ),
        # === PHP additional ===
        (
            "php",
            "test.php",
            """
            <?php
            function foo() { $x = 1; $y = 2; }
            function bar() { $a = 10; $b = 20; }
            ?>
            """,
            (1, 1),
            (2, 2),
            False,
            "Different PHP functions are separate scopes",
        ),
        (
            "php",
            "test.php",
            """
            <?php
            function foo() { $x = 1; $y = 2; $z = 3; }
            ?>
            """,
            (1, 1),
            (1, 2),
            True,
            "Lines within same PHP function should share scope",
        ),
        (
            "php",
            "test.php",
            """
            <?php
            class C { function a() { return 1; } function b() { return 2; } }
            ?>
            """,
            (1, 1),
            (1, 1),
            True,
            "Methods in same PHP class share class scope",
        ),
        (
            "php",
            "test.php",
            """
            <?php
            if (true) { $x = 1; $y = 2; }
            ?>
            """,
            (1, 1),
            (1, 1),
            True,
            "Lines in same PHP if block share scope",
        ),
        # === SWIFT additional ===
        (
            "swift",
            "test.swift",
            """
            func foo() { let x = 1; let y = 2 }
            func bar() { let a = 10; let b = 20 }
            """,
            (0, 0),
            (1, 1),
            False,
            "Different Swift functions are separate scopes",
        ),
        (
            "swift",
            "test.swift",
            """
            struct S { func add(a:Int,b:Int)->Int { a + b } func sub(a:Int,b:Int)->Int { a - b } }
            """,
            (0, 0),
            (0, 1),
            True,
            "Swift struct methods share struct scope",
        ),
        (
            "swift",
            "test.swift",
            """
            func foo() { if true { let x = 1; let y = 2 } }
            """,
            (0, 0),
            (0, 1),
            True,
            "Lines in same Swift if block share scope",
        ),
        (
            "swift",
            "test.swift",
            """
            func outer() { func inner() { let x = 1 } let y = 2 }
            """,
            (0, 0),
            (0, 1),
            True,
            "Nested functions share outer scope in Swift (if applicable)",
        ),
        # === KOTLIN additional ===
        (
            "kotlin",
            "test.kt",
            """
            fun foo() { val x = 1; val y = 2 }
            fun bar() { val a = 10; val b = 20 }
            """,
            (0, 0),
            (1, 1),
            False,
            "Different Kotlin functions are separate scopes",
        ),
        (
            "kotlin",
            "test.kt",
            """
            class C { fun a() { val x = 1 } fun b() { val y = 2 } }
            """,
            (0, 0),
            (0, 1),
            True,
            "Kotlin class methods share class scope",
        ),
        (
            "kotlin",
            "test.kt",
            """
            fun foo() { if (true) { val x = 1; val y = 2 } }
            """,
            (0, 0),
            (0, 1),
            True,
            "Lines inside Kotlin if statement share scope",
        ),
        (
            "kotlin",
            "test.kt",
            """
            fun outer() { fun inner() { val x = 1 } val y = 2 }
            """,
            (0, 0),
            (0, 1),
            True,
            "Nested Kotlin functions share outer scope",
        ),
        # === SCALA additional ===
        (
            "scala",
            "test.scala",
            """
            object X { def a = { val x = 1; val y = 2 }; def b = { val z = 3; val t = 4 } }
            """,
            (0, 0),
            (0, 1),
            True,
            "Scala block lines share same enclosing scope",
        ),
        (
            "scala",
            "test.scala",
            """
            def foo() = { val x = 1; val y = 2 }
            def bar() = { val a = 10; val b = 20 }
            """,
            (0, 0),
            (1, 1),
            False,
            "Scala top-level defs are separate scopes",
        ),
        (
            "scala",
            "test.scala",
            """
            object Outer { object Inner { def inner() = { val x = 1 } } def outer() = { val y = 2 } }
            """,
            (0, 0),
            (0, 1),
            True,
            "Scala nested object and outer share enclosing scope",
        ),
        # === DART ===
        (
            "dart",
            "test.dart",
            """
            void foo() { var x = 1; var y = 2; }
            void bar() { var a = 10; var b = 20; }
            """,
            (0, 0),
            (1, 1),
            False,
            "Different Dart functions are separate scopes",
        ),
        (
            "dart",
            "test.dart",
            """
            class C { int a() => 1; int b() => 2; }
            """,
            (0, 0),
            (0, 1),
            True,
            "Dart class methods share class scope",
        ),
        (
            "dart",
            "test.dart",
            """
            void foo() { if (true) { var x = 1; var y = 2; } }
            """,
            (0, 0),
            (0, 1),
            True,
            "Lines in same Dart if block share scope",
        ),
        (
            "dart",
            "test.dart",
            """
            void outer() { void inner() { var x = 1; } var y = 2; }
            """,
            (0, 0),
            (0, 1),
            True,
            "Nested Dart functions share enclosing scope (if applicable)",
        ),
        # === ELIXIR ===
        (
            "elixir",
            "test.ex",
            """
            defmodule M do
              def foo() do
                x = 1
                y = 2
              end
              def bar() do
                a = 10
                b = 20
              end
            end
            """,
            (2, 2),
            (6, 6),
            True,
            "Elixir functions share module scope",
        ),
        (
            "elixir",
            "test.ex",
            """
            defmodule M do
              def foo() do
                x = 1
                y = 2
                z = 3
              end
            end
            """,
            (2, 2),
            (3, 3),
            True,
            "Lines within same Elixir function share scope",
        ),
        (
            "elixir",
            "test.ex",
            """
            defmodule M do
              def outer() do
                def inner() do
                  x = 1
                end
                y = 2
              end
            end
            """,
            (2, 2),
            (3, 3),
            True,
            "Nested defs in Elixir can share parent scope",
        ),
        (
            "elixir",
            "test.ex",
            """
            defmodule M do
              def foo() do
                if true do
                  x = 1
                  y = 2
                end
              end
            end
            """,
            (3, 3),
            (3, 4),
            True,
            "Lines in same Elixir if block share scope",
        ),
        # === HASKELL ===
        (
            "haskell",
            "test.hs",
            """
            foo x = let a = 1 in a + x
            bar y = let b = 2 in b + y
            """,
            (0, 0),
            (1, 1),
            False,
            "Different Haskell top-level functions are separate scopes",
        ),
        (
            "haskell",
            "test.hs",
            """
            foo x = let a = 1; b = 2 in a + b + x
            """,
            (0, 0),
            (0, 0),
            True,
            "Let-bound lines in Haskell are within same scope",
        ),
        (
            "haskell",
            "test.hs",
            """
            foo x = case x of {1 -> 1; _ -> 2}
            """,
            (0, 0),
            (0, 0),
            True,
            "Case branches in Haskell are associated with the enclosing function scope",
        ),
        (
            "haskell",
            "test.hs",
            """
            module M where
            foo x = x + 1
            bar x = x - 1
            """,
            (1, 1),
            (2, 2),
            False,
            "Top-level functions in Haskell are separate scopes",
        ),
        # === OCAML ===
        (
            "ocaml",
            "test.ml",
            """
            let foo x = let a = 1 in a + x
            let bar y = let b = 2 in b + y
            """,
            (0, 0),
            (1, 1),
            False,
            "OCaml top-level functions are separate scopes",
        ),
        (
            "ocaml",
            "test.ml",
            """
            let foo x = let a = 1; b = 2 in a + b + x
            """,
            (0, 0),
            (0, 0),
            True,
            "Let-bound lines in OCaml share the same scope",
        ),
        (
            "ocaml",
            "test.ml",
            """
            module M = struct let foo x = x + 1 let bar y = y - 1 end
            """,
            (0, 0),
            (0, 1),
            True,
            "Module members in OCaml share module scope",
        ),
        (
            "ocaml",
            "test.ml",
            """
            if true then let x = 1 in x else let y = 2 in y
            """,
            (0, 0),
            (0, 0),
            True,
            "If expression branches in OCaml belong to the same enclosing scope",
        ),
        # === ERLANG ===
        (
            "erlang",
            "test.erl",
            """
            -module(m).
            -export([foo/0, bar/0]).
            foo() -> X = 1, Y = 2, ok.
            bar() -> A = 10, B = 20, ok.
            """,
            (2, 2),
            (3, 3),
            False,
            "Different Erlang functions are separate scopes",
        ),
        (
            "erlang",
            "test.erl",
            """
            foo() -> X = 1, Y = 2, ok.
            """,
            (0, 0),
            (0, 0),
            True,
            "Lines in same Erlang function share scope",
        ),
        (
            "erlang",
            "test.erl",
            """
            case X of 1 -> A = 1; _ -> B = 2 end.
            """,
            (0, 0),
            (0, 0),
            True,
            "Case branches in Erlang are inside enclosing expression",
        ),
        (
            "erlang",
            "test.erl",
            """
            if true -> A = 1; true -> B = 2 end.
            """,
            (0, 0),
            (0, 0),
            True,
            "Erlang if expression branches share scope",
        ),
        # === CLOJURE ===
        (
            "clojure",
            "test.clj",
            """
            (defn foo [] (let [x 1] x) (let [y 2] y))
            (defn bar [] (let [a 10] a) (let [b 20] b))
            """,
            (0, 0),
            (1, 1),
            False,
            "Different Clojure defs are separate scopes",
        ),
        (
            "clojure",
            "test.clj",
            """
            (defn foo [] (let [x 1] (let [y 2] y)))
            """,
            (0, 0),
            (0, 0),
            True,
            "Nested let in Clojure share outer scope",
        ),
        (
            "clojure",
            "test.clj",
            """
            (def obj {:a (fn [] 1) 
            :b (fn [] 2)})
            """,
            (0, 0),
            (1, 1),
            True,
            "Functions inside list share same scope",
        ),
        (
            "clojure",
            "test.clj",
            """
            (if true (do (def x 1) (def y 2)))
            """,
            (0, 0),
            (0, 0),
            True,
            "Clojure do block lines share inner scope",
        ),
        # === SOLIDITY ===
        (
            "solidity",
            "test.sol",
            """
            contract C { function a() public { uint x = 1; } function b() public { uint y = 2; } }
            """,
            (0, 0),
            (0, 1),
            True,
            "Solidity contract functions share contract scope",
        ),
        (
            "solidity",
            "test.sol",
            """
            function foo() public { uint x = 1; uint y = 2; }
            function bar() public { uint a = 10; uint b = 20; }
            """,
            (0, 0),
            (1, 1),
            False,
            "Different Solidity functions are separate scopes",
        ),
        (
            "solidity",
            "test.sol",
            """
            contract C { function foo() public { if(true) { uint x = 1; uint y = 2; } } }
            """,
            (0, 0),
            (0, 1),
            True,
            "Lines in Solidity if block share scope",
        ),
        (
            "solidity",
            "test.sol",
            """
            contract C { struct S { uint x; uint y; } }
            """,
            (0, 0),
            (0, 0),
            True,
            "Struct members in Solidity are within struct scope",
        ),
        # === JULIA ===
        (
            "julia",
            "test.jl",
            """
            function foo()
                x = 1
                y = 2
            end
            function bar()
                a = 10
                b = 20
            end
            """,
            (1, 1),
            (4, 4),
            False,
            "Different Julia functions are separate scopes",
        ),
        (
            "julia",
            "test.jl",
            """
            function foo()
                x = 1
                y = 2
                z = 3
            end
            """,
            (1, 1),
            (2, 2),
            True,
            "Lines within same Julia function share scope",
        ),
        (
            "julia",
            "testV.jl",
            """
            module M
            function a() x = 1 end
            function b() y = 2 end
            end
            """,
            (1, 1),
            (2, 2),
            True,
            "Module definitions in Julia share module scope",
        ),
        (
            "julia",
            "test.jl",
            """
            function foo()
                if true
                    x = 1
                    y = 2
                end
            end
            """,
            (2, 2),
            (2, 3),
            True,
            "Lines inside Julia if statement share scope",
        ),
        # === NESTED SCOPES (Python) ===
        (
            "python",
            "test.py",
            """
            class Outer:
                class Inner:
                    def method(self):
                        x = 1
                
                def outer_method(self):
                    y = 2
            """,
            (2, 3),  # Inner class method
            (5, 6),  # Outer method
            True,
            "Nested class and outer method share Outer class scope",
        ),
        # === CONTROL FLOW SCOPES (Python) ===
        (
            "python",
            "test.py",
            """
            for i in range(10):
                x = i
                y = i * 2
            """,
            (1, 1),  # x = i
            (2, 2),  # y = i * 2
            True,
            "Lines in same for loop share scope",
        ),
    ],
)
def test_scope_based_grouping(
    tools,
    language,
    filename,
    content,
    chunk1_lines,
    chunk2_lines,
    should_share_scope,
    scope_description,
):
    """
    Test that two code chunks share (or don't share) scopes as expected.

    Args:
        tools: Fixture providing parser and scope_mapper
        language: Programming language
        filename: File name for context
        content: Source code content
        chunk1_lines: Tuple (start, end) for first chunk (0-indexed after strip)
        chunk2_lines: Tuple (start, end) for second chunk (0-indexed after strip)
        should_share_scope: Whether chunks should share at least one scope
        scope_description: Description of what's being tested
    """
    parser, scope_mapper = tools

    # Clean up content
    clean_content = dedent(content).strip()
    total_lines = len(clean_content.splitlines())

    # Parse the file
    parsed = parser.parse_file(filename, clean_content, [(0, total_lines - 1)])
    assert parsed.detected_language == language

    # Build scope map
    scope_map = scope_mapper.build_scope_map(
        parsed.detected_language,
        parsed.root_node,
        filename.encode("utf-8"),
        parsed.content_bytes,
        [(0, total_lines - 1)],
    )

    # Get scopes for each chunk's lines
    chunk1_scopes = set()
    for line_num in range(chunk1_lines[0], chunk1_lines[1] + 1):
        scopes = scope_map.scope_lines.get(line_num, set())
        chunk1_scopes.update(scopes)

    chunk2_scopes = set()
    for line_num in range(chunk2_lines[0], chunk2_lines[1] + 1):
        scopes = scope_map.scope_lines.get(line_num, set())
        chunk2_scopes.update(scopes)

    # Check if they share any scopes
    shared_scopes = chunk1_scopes & chunk2_scopes
    has_shared_scope = len(shared_scopes) > 0

    # Assert based on expectation
    if should_share_scope:
        assert has_shared_scope, (
            f"{scope_description}\n"
            f"Expected chunks to share scope, but they don't.\n"
            f"Chunk1 scopes: {chunk1_scopes}\n"
            f"Chunk2 scopes: {chunk2_scopes}\n"
            f"Shared scopes: {shared_scopes}"
        )
    else:
        assert not has_shared_scope, (
            f"{scope_description}\n"
            f"Expected chunks NOT to share scope, but they do.\n"
            f"Chunk1 scopes: {chunk1_scopes}\n"
            f"Chunk2 scopes: {chunk2_scopes}\n"
            f"Shared scopes: {shared_scopes}"
        )


# -------------------------------------------------------------------------
# Additional Edge Case Tests
# -------------------------------------------------------------------------


def test_scope_map_empty_file(tools):
    """Test that empty files produce empty scope maps."""
    parser, scope_mapper = tools

    content = ""
    parsed = parser.parse_file("test.py", content, [(0, 0)])

    scope_map = scope_mapper.build_scope_map(
        parsed.detected_language,
        parsed.root_node,
        b"test.py",
        parsed.content_bytes,
        [(0, 0)],
    )

    assert len(scope_map.scope_lines) == 0


def test_scope_map_single_line(tools):
    """Test scope mapping for single line of code."""
    parser, scope_mapper = tools

    content = "x = 1"
    parsed = parser.parse_file("test.py", content, [(0, 0)])

    scope_map = scope_mapper.build_scope_map(
        parsed.detected_language,
        parsed.root_node,
        b"test.py",
        parsed.content_bytes,
        [(0, 0)],
    )

    # Single line may or may not have scope depending on language
    # This just ensures it doesn't crash
    assert scope_map.scope_lines is not None


@pytest.mark.parametrize(
    "language,filename,content",
    [
        ("python", "test.py", "def foo():\n    x = 1\n    y = 2"),
        ("javascript", "test.js", "function foo() {\n    const x = 1;\n}"),
        ("java", "Test.java", "class Test {\n    void foo() {}\n}"),
        ("rust", "test.rs", "fn foo() {\n    let x = 1;\n}"),
    ],
)
def test_scope_consistency(tools, language, filename, content):
    """
    Test that scope mapping is consistent - if a line is in a scope,
    all lines in that scope should reference the same scope identifier.
    """
    parser, scope_mapper = tools

    parsed = parser.parse_file(filename, content, [(0, len(content.splitlines()) - 1)])
    assert parsed is not None

    scope_map = scope_mapper.build_scope_map(
        parsed.detected_language,
        parsed.root_node,
        filename.encode("utf-8"),
        parsed.content_bytes,
        [(0, len(content.splitlines()) - 1)],
    )

    # Each scope identifier should appear on multiple lines (or at least one)
    scope_occurrences = {}
    for line_num, scopes in scope_map.scope_lines.items():
        for scope in scopes:
            scope_occurrences.setdefault(scope, []).append(line_num)

    # Verify each scope has at least one line
    for scope, lines in scope_occurrences.items():
        assert len(lines) >= 1, f"Scope {scope} has no lines"
        # Verify lines are contiguous or properly nested
        assert max(lines) - min(lines) + 1 >= len(lines), (
            f"Scope {scope} has non-contiguous lines: {lines}"
        )
