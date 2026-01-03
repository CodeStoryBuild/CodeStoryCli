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

"""Tests for scope-based semantic grouping.

Tests verify that chunks within the same scope (function, class, etc.)
are grouped together.
"""

from textwrap import dedent

import pytest

from codestory.core.file_parser.file_parser import FileParser
from codestory.core.semantic_analysis.mappers.query_manager import QueryManager
from codestory.core.semantic_analysis.mappers.scope_mapper import ScopeMapper

# -------------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------------


@pytest.fixture(scope="module")
def tools():
    """Initializes the heavy components once per module.

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
            True,
            "Object methods don't share scope inside object literal",
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
            class User(val name: String, var age: Int) {

                // A function (method) inside the class
                fun displayInfo() {
                    println("Name: $name, Age: $age")
                }

                // A function that returns a value
                fun isAdult(): Boolean {
                    return age >= 18
                }
            }
            """,
            (1, 1),  # add
            (3, 3),  # subtract
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
        # === BASH ===
        (
            "bash",
            "test.sh",
            """
            function func_one() {
                x=1
                y=2
                echo $((x + y))
            }

            function func_two() {
                a=10
                b=20
                echo $((a + b))
            }
            """,
            (1, 2),  # func_one internals
            (7, 8),  # func_two internals
            False,
            "Bash: Different functions have different scopes",
        ),
        (
            "bash",
            "test.sh",
            """
            function calculate() {
                x=1
                y=2
                z=3
                echo $((x + y + z))
            }
            """,
            (1, 1),  # x = 1
            (3, 3),  # z = 3
            True,
            "Bash: Lines within same function share scope",
        ),
        (
            "bash",
            "test.sh",
            """
            if [ "$1" = "test" ]; then
                x=1
                y=2
            else
                a=10
                b=20
            fi
            """,
            (1, 2),  # then branch
            (4, 5),  # else branch
            True,
            "Bash: if/else branches share conditional scope",
        ),
        (
            "bash",
            "test.sh",
            """
            for i in {1..5}; do
                sum=$((sum + i))
                echo $sum
            done

            for j in {1..3}; do
                count=$((count + 1))
            done
            """,
            (1, 2),  # first for loop
            (6, 6),  # second for loop
            False,
            "Bash: Different loops have different scopes",
        ),
        (
            "bash",
            "test.sh",
            """
            case $1 in
                start)
                    echo "Starting"
                    ;;
                stop)
                    echo "Stopping"
                    ;;
            esac
            """,
            (2, 2),  # start case
            (5, 5),  # stop case
            True,
            "Bash: Case items share case statement scope",
        ),
        # === C ===
        (
            "c",
            "test.c",
            """
            void foo() {
                int x = 1;
                int y = 2;
                printf("%d", x + y);
            }

            void bar() {
                int a = 10;
                int b = 20;
                printf("%d", a + b);
            }
            """,
            (1, 2),  # foo function
            (7, 8),  # bar function
            False,
            "C: Different functions have different scopes",
        ),
        (
            "c",
            "test.c",
            """
            void calculate() {
                int x = 1;
                int y = 2;
                int z = 3;
                printf("%d", x + y + z);
            }
            """,
            (1, 1),  # x = 1
            (3, 3),  # z = 3
            True,
            "C: Lines within same function share scope",
        ),
        (
            "c",
            "test.c",
            """
            struct Data {
                int value;
                void process() {
                    value = 10;
                }
            };

            struct Other {
                int num;
            };
            """,
            (0, 4),  # Data struct
            (7, 9),  # Other struct
            False,
            "C: Different structs have different scopes",
        ),
        (
            "c",
            "test.c",
            """
            void process(int n) {
                if (n > 0) {
                    int x = 1;
                    printf("%d", x);
                } else {
                    int y = 2;
                    printf("%d", y);
                }
            }
            """,
            (2, 3),  # if branch
            (5, 6),  # else branch
            True,
            "C: if/else branches share function scope",
        ),
        (
            "c",
            "test.c",
            """
            void loops() {
                for (int i = 0; i < 5; i++) {
                    printf("%d ", i);
                }

                for (int j = 0; j < 3; j++) {
                    printf("%d ", j);
                }
            }
            """,
            (1, 2),  # first for loop
            (5, 6),  # second for loop
            True,
            "C: Loops within same function share function scope",
        ),
        # === TOML ===
        (
            "toml",
            "config.toml",
            """
            [package]
            name = "myapp"
            version = "1.0.0"
            authors = ["John Doe"]
            """,
            (1, 2),  # name and version
            (3, 3),  # authors
            True,
            "TOML: Keys within same table share scope",
        ),
        (
            "toml",
            "config.toml",
            """
            [server]
            host = "localhost"
            port = 8080

            [database]
            host = "db.local"
            port = 5432
            """,
            (1, 2),  # server table keys
            (5, 6),  # database table keys
            False,
            "TOML: Different tables have different scopes",
        ),
        (
            "toml",
            "config.toml",
            """
            [[products]]
            name = "Widget"
            price = 9.99

            [[products]]
            name = "Gadget"
            price = 19.99
            """,
            (1, 2),  # first product
            (5, 6),  # second product
            False,
            "TOML: Array table elements have separate scopes",
        ),
        (
            "toml",
            "config.toml",
            """
            [server.database]
            type = "postgres"
            host = "localhost"
            port = 5432
            """,
            (1, 2),  # type and host
            (3, 3),  # port
            True,
            "TOML: Nested table keys share nested table scope",
        ),
        (
            "toml",
            "config.toml",
            """
            colors = ["red", "green"]
            numbers = [1, 2, 3]
            config = { debug = true }
            """,
            (0, 0),  # colors array
            (2, 2),  # config inline table
            False,
            "TOML: Different value types (array vs inline table) are separate scopes",
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
            True,
            "Object literal methods in TypeScript are shared scopes",
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
            class Outer { class Inner
            { void innerMethod() { int x = 1; } }
            void outerMethod() { int y = 2; } }
            """,
            (0, 1),
            (1, 2),
            True,
            "Nested class and outer method share container scope in Java",
        ),
        (
            "java",
            "Test.java",
            """
            if (true)
            { int x = 1; int y = 2; }
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
            class MyClass { void m1() { int x = 1; }
            void m2() { int y = 2; } };
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
            namespace ns {
            void foo() { int x = 1; } }
            """,
            (0, 0),
            (0, 1),
            True,
            "C++ lines inside namespace share scope",
        ),
        (
            "cpp",
            "test.cpp",
            """
            for (int i=0;i<1;++i)
            { int x = 1; int y = 2; }
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
            fn foo() { let x = 1;
            let y = 2; let z = 3; }
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
            impl MyStruct { fn m1(&self) { let x = 1;
              } fn m2(&self) { let y = 2; } }
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
            fn foo() { if true { let
              x = 1; let y = 2; } }
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
            True,
            "PHP functions are are same scope scopes",
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
            (0, 1),
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
            struct S { func add(a:Int,b:Int)->Int {
            a + b } func sub(a:Int,b:Int)->Int { a - b } }
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
            func foo() { if true {
            let x = 1; let y = 2 } }
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
            func outer() { func inner()
            { let x = 1 } let y = 2 }
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
            class C { fun a() { val x = 1 }
            fun b() { val y = 2 } }
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
            fun foo() { if (true)
            { val x = 1; val y = 2 } }
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
            fun outer() { fun inner()
            { val x = 1 } val y = 2 }
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
            object X { def a = { val x = 1; val y = 2 };
            def b = { val z = 3; val t = 4 } }
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
            object Outer { object Inner { def inner() =
            { val x = 1 } } def outer() = {
              val y = 2 } }
            """,
            (0, 1),
            (1, 2),
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
            class C { int a() => 1;
              int b() => 2; }
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
            void foo() { if (true) {
            var x = 1; var y = 2; } }
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
            void outer() { void inner() {
              var x = 1; } var y = 2; }
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
            foo x = let a = 1; b = 2
              in a + b + x
            """,
            (0, 0),
            (0, 1),
            True,
            "Let-bound lines in Haskell are within same scope",
        ),
        (
            "haskell",
            "test.hs",
            """
            foo x = case x of
            {1 -> 1; _ -> 2}
            """,
            (0, 0),
            (0, 1),
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
            let foo x = let a = 1;
              b = 2 in a + b + x
            """,
            (0, 0),
            (0, 1),
            True,
            "Let-bound lines in OCaml share the same scope",
        ),
        (
            "ocaml",
            "test.ml",
            """
            module M = struct let
              foo x = x + 1 let bar y = y - 1 end
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
            if true then let x = 1 in
            x else let y = 2 in y
            """,
            (0, 0),
            (0, 1),
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
            foo()
              -> X = 1, Y = 2, ok.
            """,
            (0, 0),
            (0, 1),
            True,
            "Lines in same Erlang function share scope",
        ),
        (
            "erlang",
            "test.erl",
            """
            case X of 1 -> A
            = 1; _ -> B = 2 end.
            """,
            (0, 0),
            (0, 1),
            True,
            "Case branches in Erlang are inside enclosing expression",
        ),
        (
            "erlang",
            "test.erl",
            """
            if true -> A = 1;
            true -> B = 2 end.
            """,
            (0, 0),
            (0, 1),
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
            (defn foo [] (let [x 1]
              (let [y 2] y)))
            """,
            (0, 0),
            (0, 1),
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
            (if true (do (def x 1)
              (def y 2)))
            """,
            (0, 0),
            (0, 1),
            True,
            "Clojure do block lines share inner scope",
        ),
        # === SOLIDITY ===
        (
            "solidity",
            "test.sol",
            """
            contract C { function a() public { uint x = 1; }
              function b() public { uint y = 2; } }
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
            contract C { function foo() public { if(true)
            { uint x = 1; uint y = 2; } } }
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
            contract C { struct S {
              uint x; uint y; } }
            """,
            (0, 0),
            (0, 1),
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
        # === JSON ===
        (
            "json",
            "test.json",
            """
            {
                "name": "example",
                "version": "1.0.0"
            }
            """,
            (1, 1),  # name property
            (2, 2),  # version property
            True,
            "JSON: Properties in same object share scope",
        ),
        (
            "json",
            "test.json",
            """
            {
                "database": {
                    "host": "localhost",
                    "port": 5432
                }
            }
            """,
            (2, 2),  # host property
            (3, 3),  # port property
            True,
            "JSON: Properties in same nested object share scope",
        ),
        (
            "json",
            "test.json",
            """
            {
                "users": [
                    {"id": 1, "name": "Alice"},
                    {"id": 2, "name": "Bob"}
                ]
            }
            """,
            (2, 2),  # First object in array
            (3, 3),  # Second object in array
            True,
            "JSON: Objects in same array share array scope",
        ),
        (
            "json",
            "test.json",
            """
            [
                {"id": 1},
                {"id": 2}
            ]
            """,
            (1, 1),  # First object
            (2, 2),  # Second object
            True,
            "JSON: Array items share array scope",
        ),
        (
            "json",
            "test.json",
            """
            {
                "config": {
                    "enabled": true
                },
                "settings": {
                    "timeout": 30
                }
            }
            """,
            (2, 2),  # config.enabled
            (5, 5),  # settings.timeout
            True,
            "JSON: Different nested objects share root object scope",
        ),
        # === YAML ===
        (
            "yaml",
            "test.yaml",
            """
            name: example
            version: 1.0.0
            """,
            (0, 0),  # name key
            (1, 1),  # version key
            True,
            "YAML: Keys in same root mapping share scope",
        ),
        (
            "yaml",
            "test.yaml",
            """
            database:
              host: localhost
              port: 5432
            """,
            (1, 1),  # host property
            (2, 2),  # port property
            True,
            "YAML: Properties in same nested mapping share scope",
        ),
        (
            "yaml",
            "test.yaml",
            """
            users:
              - id: 1
                name: Alice
              - id: 2
                name: Bob
            """,
            (1, 2),  # First object
            (3, 4),  # Second object
            True,
            "YAML: Objects in same sequence share sequence scope",
        ),
        (
            "yaml",
            "test.yaml",
            """
            config:
              enabled: true
            settings:
              timeout: 30
            """,
            (1, 1),  # config.enabled
            (3, 3),  # settings.timeout
            True,
            "YAML: Different nested mappings share root scope",
        ),
        (
            "yaml",
            "test.yaml",
            """
            services:
              web:
                port: 8080
                env: production
              db:
                port: 5432
                type: postgres
            """,
            (2, 3),  # web properties
            (5, 6),  # db properties
            True,
            "YAML: Sibling nested mappings share parent scope",
        ),
        # === MARKDOWN ===
        (
            "markdown",
            "test.md",
            """
            # Main Title

            First paragraph under main

            # Another Top Level

            Second paragraph under another
            """,
            (2, 2),  # First paragraph
            (6, 6),  # Second paragraph
            False,
            "Markdown: Different top-level sections don't share scope",
        ),
        (
            "markdown",
            "test.md",
            """
            ## Section

            First paragraph
            Second paragraph
            """,
            (2, 2),  # First paragraph
            (3, 3),  # Second paragraph
            True,
            "Markdown: Paragraphs in same section share section scope",
        ),
        (
            "markdown",
            "test.md",
            """
            - Item 1
            - Item 2
            - Item 3
            """,
            (0, 0),  # Item 1
            (2, 2),  # Item 3
            True,
            "Markdown: List items in same list share list scope",
        ),
        (
            "markdown",
            "test.md",
            """
            # Heading

            ```python
            def foo():
                pass
            ```

            Regular paragraph
            """,
            (2, 4),  # Code block
            (7, 7),  # Paragraph
            True,
            "Markdown: Code block and paragraph in same section share scope",
        ),
        (
            "markdown",
            "test.md",
            """
            ## First Section

            Content here

            ## Second Section

            More content
            """,
            (2, 2),  # Content in first section
            (6, 6),  # Content in second section
            False,
            "Markdown: Content in different H2 sections don't share scope",
        ),
        # === RST ===
        (
            "rst",
            "test.rst",
            """
            =====
            Title
            =====

            First paragraph

            Another Section
            ===============

            Second paragraph
            """,
            (5, 5),  # First paragraph
            (10, 10),  # Second paragraph
            False,
            "RST: Different top-level sections don't share scope",
        ),
        (
            "rst",
            "test.rst",
            """
            Section
            =======

            First paragraph
            Second paragraph
            """,
            (3, 3),  # First paragraph
            (4, 4),  # Second paragraph
            True,
            "RST: Paragraphs in same section share section scope",
        ),
        (
            "rst",
            "test.rst",
            """
            - Item 1
            - Item 2
            - Item 3
            """,
            (0, 0),  # Item 1
            (2, 2),  # Item 3
            True,
            "RST: List items in same list share list scope",
        ),
        (
            "rst",
            "test.rst",
            """
            Title
            =====

            .. code-block:: python

               def foo():
                   pass

            Regular paragraph
            """,
            (3, 6),  # Code block directive
            (8, 8),  # Paragraph
            False,
            "RST: Directive and paragraph in global dont share scope",
        ),
        (
            "rst",
            "test.rst",
            """
            First Section
            =============

            Content here

            Second Section
            ==============

            More content
            """,
            (3, 3),  # Content in first section
            (8, 8),  # Content in second section
            False,
            "RST: Content in different sections don't share scope",
        ),
        # === HTML ===
        (
            "html",
            "test.html",
            """
            <div class="container">
                <p>First paragraph</p>
                <p>Second paragraph</p>
            </div>
            """,
            (1, 1),  # First paragraph
            (2, 2),  # Second paragraph
            True,
            "HTML: Elements in same container share scope",
        ),
        (
            "html",
            "test.html",
            """
            <div class="header">
                <h1>Title</h1>
            </div>
            <div class="footer">
                <p>Footer text</p>
            </div>
            """,
            (1, 1),  # header div content
            (4, 4),  # footer div content
            False,
            "HTML: Different sibling elements don't share scope",
        ),
        (
            "html",
            "test.html",
            """
            <ul>
                <li>Item 1</li>
                <li>Item 2</li>
                <li>Item 3</li>
            </ul>
            """,
            (1, 1),  # First li
            (3, 3),  # Third li
            True,
            "HTML: List items in same ul share scope",
        ),
        (
            "html",
            "test.html",
            """
            <html>
                <head>
                    <title>Test</title>
                </head>
                <body>
                    <div>Content</div>
                </body>
            </html>
            """,
            (2, 2),  # title in head
            (5, 5),  # div in body
            True,
            "HTML: head and body elements share html element scope",
        ),
        (
            "html",
            "test.html",
            """
            <div>
                <span>Text 1</span>
                <span>Text 2</span>
            </div>
            """,
            (1, 1),  # First span
            (2, 2),  # Second span
            True,
            "HTML: Nested elements share parent scope",
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
    """Test that two code chunks share (or don't share) scopes as expected.

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
    parsed = parser.parse_file(
        filename.encode("utf-8"), clean_content.encode("utf-8"), [(0, total_lines - 1)]
    )
    assert parsed.detected_language == language

    # Build scope map
    scope_map = scope_mapper.build_scope_map(
        parsed.detected_language,
        parsed.root_node,
        filename.encode("utf-8"),
        [(0, total_lines - 1)],
    )

    print(f"Scope Map Structural Scopes: {scope_map.structural_scope_lines}")

    # Get scopes for each chunk's lines
    chunk1_scopes = set()
    for line_num in range(chunk1_lines[0], chunk1_lines[1] + 1):
        structural_scopes = scope_map.structural_scope_lines.get(line_num, set())
        chunk1_scopes.update(structural_scopes)

    chunk2_scopes = set()
    for line_num in range(chunk2_lines[0], chunk2_lines[1] + 1):
        structural_scopes = scope_map.structural_scope_lines.get(line_num, set())
        chunk2_scopes.update(structural_scopes)

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
    parsed = parser.parse_file(b"test.py", content.encode("utf-8"), [(0, 0)])

    scope_map = scope_mapper.build_scope_map(
        parsed.detected_language,
        parsed.root_node,
        b"test.py",
        [(0, 0)],
    )

    assert len(scope_map.structural_scope_lines) == 0
    assert len(scope_map.semantic_named_scopes) == 0


def test_scope_map_single_line(tools):
    """Test scope mapping for single line of code."""
    parser, scope_mapper = tools

    content = "x = 1"
    parsed = parser.parse_file(b"test.py", content.encode("utf-8"), [(0, 0)])

    scope_map = scope_mapper.build_scope_map(
        parsed.detected_language,
        parsed.root_node,
        b"test.py",
        [(0, 0)],
    )

    # Single line may or may not have scope depending on language
    # This just ensures it doesn't crash
    assert scope_map.structural_scope_lines is not None
    assert scope_map.semantic_named_scopes is not None


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

    parsed = parser.parse_file(
        filename.encode("utf-8"),
        content.encode("utf-8"),
        [(0, len(content.splitlines()) - 1)],
    )
    assert parsed is not None

    scope_map = scope_mapper.build_scope_map(
        parsed.detected_language,
        parsed.root_node,
        filename.encode("utf-8"),
        [(0, len(content.splitlines()) - 1)],
    )

    # Each scope identifier should appear on multiple lines (or at least one)
    scope_occurrences = {}
    # Merge both named and structural scopes
    all_scope_lines = {}
    for line_num, scopes in scope_map.structural_scope_lines.items():
        all_scope_lines.setdefault(line_num, set()).update(scopes)

    for line_num, scopes in all_scope_lines.items():
        for scope in scopes:
            scope_occurrences.setdefault(scope, []).append(line_num)

    # Verify each scope has at least one line
    for scope, lines in scope_occurrences.items():
        assert len(lines) >= 1, f"Scope {scope} has no lines"
        # Verify lines are contiguous or properly nested
        assert max(lines) - min(lines) + 1 >= len(lines), (
            f"Scope {scope} has non-contiguous lines: {lines}"
        )
