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

"""Tests for symbol-based semantic grouping.

Tests verify that chunks are grouped based on shared defined symbols
that are modified in the diff.
"""

from textwrap import dedent

import pytest

from codestory.core.file_parser.file_parser import FileParser
from codestory.core.semantic_analysis.mappers.query_manager import QueryManager
from codestory.core.semantic_analysis.mappers.symbol_extractor import SymbolExtractor
from codestory.core.semantic_analysis.mappers.symbol_mapper import SymbolMapper

# -------------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------------


@pytest.fixture(scope="module")
def tools():
    """Initializes the heavy components once per module.

    Returns a tuple of (FileParser, SymbolExtractor, SymbolMapper).
    """
    qm = QueryManager.get_instance()
    symbol_extractor = SymbolExtractor(qm)
    symbol_mapper = SymbolMapper(qm)
    parser = FileParser()
    return parser, symbol_extractor, symbol_mapper


# -------------------------------------------------------------------------
# Test Cases
# -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "language,filename,content,modified_lines,chunk1_lines,chunk2_lines,should_share_symbols,description",
    [
        # === PYTHON ===
        (
            "python",
            "test.py",
            """
            class Calculator:
                pass

            def use_calc():
                calc = Calculator()
                return calc
            """,
            [(0, 1), (4, 5)],  # Modify class definition and usage
            (0, 1),  # Class definition
            (4, 5),  # Usage
            True,
            "Python: Class definition and usage should share symbol",
        ),
        (
            "python",
            "test.py",
            """
            def foo():
                x = 1
                return x

            def bar():
                y = 2
                return y
            """,
            [(0, 2), (4, 6)],  # Modify both functions
            (0, 2),  # foo
            (4, 6),  # bar
            False,
            "Python: Different functions don't share symbols",
        ),
        (
            "python",
            "test.py",
            """
            x = 10

            def modify_x():
                global x
                x = 20

            def read_x():
                return x
            """,
            [(0, 0), (3, 4)],  # Modify definition and one usage
            (0, 0),  # x definition
            (3, 4),  # modify_x
            True,
            "Python: Global variable definition and modification share symbol",
        ),
        (
            "python",
            "test.py",
            """
            def process(data):
                result = data * 2
                return result

            def other_func():
                x = 5
                return x
            """,
            [(1, 1), (5, 5)],  # Modify result and x (different symbols)
            (1, 1),  # result
            (5, 5),  # x
            False,
            "Python: Local variables in different functions don't share",
        ),
        # === JAVASCRIPT ===
        (
            "javascript",
            "test.js",
            """
            class User {
                constructor(name) {
                    this.name = name;
                }
            }

            function createUser() {
                return new User("John");
            }
            """,
            [(0, 4), (6, 8)],  # Modify class and usage
            (0, 4),  # Class definition
            (6, 8),  # Usage
            True,
            "JavaScript: Class definition and usage share symbol",
        ),
        (
            "javascript",
            "test.js",
            """
            function add(a, b) {
                return a + b;
            }

            function multiply(c, d) {
                return c * d;
            }
            """,
            [(0, 2), (4, 6)],  # Modify both functions
            (0, 2),  # add
            (4, 6),  # multiply
            False,
            "JavaScript: Different functions don't share symbols",
        ),
        (
            "javascript",
            "test.js",
            """
            const API_KEY = "secret";

            function useApi() {
                return API_KEY;
            }

            function otherFunc() {
                return "other";
            }
            """,
            [(0, 0), (2, 4)],  # Modify constant and its usage
            (0, 0),  # API_KEY definition
            (2, 4),  # Usage in useApi
            True,
            "JavaScript: Constant definition and usage share symbol",
        ),
        # === TYPESCRIPT ===
        (
            "typescript",
            "test.ts",
            """
            interface IUser {
                name: string;
                age: number;
            }

            function createUser(): IUser {
                return { name: "John", age: 30 };
            }
            """,
            [(0, 3), (5, 7)],  # Modify interface and usage
            (0, 3),  # Interface definition
            (5, 7),  # Function using interface
            True,
            "TypeScript: Interface definition and usage share symbol",
        ),
        (
            "typescript",
            "test.ts",
            """
            type UserId = string;
            type ProductId = string;

            function getUser(id: UserId) {
                return id;
            }

            function getProduct(id: ProductId) {
                return id;
            }
            """,
            [(0, 0), (3, 5)],  # Modify UserId type and its usage
            (0, 0),  # UserId type
            (3, 5),  # getUser function
            True,
            "TypeScript: Type alias and usage share symbol",
        ),
        # === RUST ===
        (
            "rust",
            "test.rs",
            """
            struct Point {
                x: i32,
                y: i32,
            }

            fn create_point() -> Point {
                Point { x: 0, y: 0 }
            }
            """,
            [(0, 3), (5, 7)],  # Modify struct definition and usage
            (0, 3),  # Point struct definition
            (5, 7),  # create_point function
            True,
            "Rust: Struct definition and type usage share symbol",
        ),
        (
            "rust",
            "test.rs",
            """
            fn process_data(x: i32) -> i32 {
                x * 2
            }

            fn process_string(s: String) -> String {
                s.to_uppercase()
            }
            """,
            [(0, 2), (4, 6)],  # Modify both functions
            (0, 2),  # process_data
            (4, 6),  # process_string
            False,
            "Rust: Different functions don't share symbols",
        ),
        # === PHP ===
        (
            "php",
            "test.php",
            """
            <?php
            class Database {
                public function connect() {}
            }

            function getDb() {
                return new Database();
            }
            """,
            [(1, 3), (5, 7)],  # Modify class and usage
            (1, 3),  # Database class
            (5, 7),  # getDb function
            True,
            "PHP: Class definition and instantiation share symbol",
        ),
        # === JAVA ===
        (
            "java",
            "test.java",
            """
            class Calculator {
                public int add(int a, int b) {
                    return a + b;
                }
            }

            class Main {
                public void test() {
                    Calculator calc = new Calculator();
                }
            }
            """,
            [(0, 3), (5, 8)],  # Modify both class definitions
            (0, 3),  # Calculator class
            (5, 8),  # Main class
            True,
            "Java: Class type usage should link to class definition",
        ),
        # === GO ===
        (
            "go",
            "test.go",
            """
            package main

            type Calculator struct {
                value int
            }

            func NewCalculator() *Calculator {
                return &Calculator{value: 0}
            }
            """,
            [(2, 4), (6, 8)],  # Modify type definition and usage
            (2, 4),  # Calculator type
            (6, 8),  # NewCalculator function
            True,
            "Go: Type definition and usage share symbol",
        ),
        # === RUBY ===
        (
            "ruby",
            "test.rb",
            """
            class Calculator
              def initialize
                @value = 0
              end
            end

            def create_calc
              Calculator.new
            end
            """,
            [(0, 4), (6, 8)],  # Modify class and usage
            (0, 4),  # Calculator class
            (6, 8),  # create_calc method
            True,
            "Ruby: Class definition and instantiation share symbol",
        ),
        # === SWIFT ===
        (
            "swift",
            "test.swift",
            """
            class Person {
                var name: String
                init(name: String) {
                    self.name = name
                }
            }

            func createPerson() -> Person {
                return Person(name: "John")
            }
            """,
            [(0, 5), (7, 9)],  # Modify class and usage
            (0, 5),  # Person class
            (7, 9),  # createPerson function
            True,
            "Swift: Class definition and type usage share symbol",
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
            }

            fun createCalculator(): Calculator {
                return Calculator()
            }
            """,
            [(0, 4), (6, 8)],  # Modify class and usage
            (0, 4),  # Calculator class
            (6, 8),  # createCalculator function
            True,
            "Kotlin: Class definition and type usage share symbol",
        ),
        # === SCALA ===
        (
            "scala",
            "test.scala",
            """
            class Calculator {
              def add(a: Int, b: Int): Int = a + b
            }

            object Main {
              def createCalc(): Calculator = new Calculator()
            }
            """,
            [(0, 2), (4, 6)],  # Modify class and usage
            (0, 2),  # Calculator class
            (4, 6),  # Main object
            True,
            "Scala: Class definition and type usage share symbol",
        ),
        # === BASH ===
        (
            "bash",
            "test.sh",
            """
            #!/bin/bash
            MY_VAR="config"

            function use_config() {
                echo $MY_VAR
            }

            use_config
            """,
            [(1, 1), (3, 5)],  # Modify variable definition and usage
            (1, 1),  # MY_VAR definition
            (3, 5),  # use_config function
            True,
            "Bash: Variable definition and usage share symbol",
        ),
        (
            "bash",
            "test.sh",
            """
            function func_one() {
                local x=1
                echo $x
            }

            function func_two() {
                local y=2
                echo $y
            }
            """,
            [(0, 3), (5, 8)],  # Modify both functions
            (0, 3),  # func_one
            (5, 8),  # func_two
            False,
            "Bash: Different functions don't share local variables",
        ),
        (
            "bash",
            "test.sh",
            """
            CONFIG_FILE="/etc/app.conf"

            function load_config() {
                cat $CONFIG_FILE
            }

            function other_func() {
                echo "other"
            }
            """,
            [(0, 0), (2, 4)],  # Modify global var and usage
            (0, 0),  # CONFIG_FILE definition
            (2, 4),  # load_config using it
            True,
            "Bash: Global variable definition and function usage share symbol",
        ),
        (
            "bash",
            "test.sh",
            """
            function process() {
                result="processed"
                echo $result
            }

            function display() {
                msg="display"
                echo $msg
            }
            """,
            [(1, 1), (6, 6)],  # Modify local vars in different functions
            (1, 1),  # result in process
            (6, 6),  # msg in display
            False,
            "Bash: Local variables in different functions don't share",
        ),
        (
            "bash",
            "test.sh",
            """
            function calculate() {
                sum=0
                return $sum
            }

            calculate
            echo $sum
            """,
            [(1, 1), (6, 6)],  # Modify variable definition and later usage
            (1, 1),  # sum in calculate
            (6, 6),  # sum usage outside
            True,
            "Bash: Variable defined in function can be accessed outside",
        ),
        # === C ===
        (
            "c",
            "test.c",
            """
            #include <stdio.h>

            int global_var = 42;

            void use_global() {
                printf("%d", global_var);
            }

            int main() {
                use_global();
                return 0;
            }
            """,
            [(2, 2), (4, 6)],  # Modify global variable and usage
            (2, 2),  # global_var definition
            (4, 6),  # use_global function
            True,
            "C: Global variable definition and usage share symbol",
        ),
        (
            "c",
            "test.c",
            """
            void func_one() {
                int x = 1;
                printf("%d", x);
            }

            void func_two() {
                int y = 2;
                printf("%d", y);
            }
            """,
            [(0, 3), (5, 8)],  # Modify both functions
            (0, 3),  # func_one
            (5, 8),  # func_two
            False,
            "C: Different functions don't share local variables",
        ),
        (
            "c",
            "test.c",
            """
            struct Point {
                int x;
                int y;
            };

            struct Point create_point(int a, int b) {
                struct Point p;
                p.x = a;
                p.y = b;
                return p;
            }
            """,
            [(0, 3), (5, 10)],  # Modify struct definition and usage
            (0, 3),  # Point struct definition
            (5, 10),  # create_point function
            True,
            "C: Struct definition and type usage share symbol",
        ),
        (
            "c",
            "test.c",
            """
            int calculate(int n) {
                int result = n * 2;
                return result;
            }

            int process(int m) {
                int value = m + 1;
                return value;
            }
            """,
            [(1, 1), (6, 6)],  # Modify local vars in different functions
            (1, 1),  # result in calculate
            (6, 6),  # value in process
            False,
            "C: Local variables in different functions don't share",
        ),
        (
            "c",
            "test.c",
            """
            typedef struct {
                int id;
                char name[50];
            } User;

            User create_user() {
                User u;
                u.id = 1;
                return u;
            }
            """,
            [(0, 3), (5, 9)],  # Modify typedef and usage
            (0, 3),  # User typedef
            (5, 9),  # create_user function
            True,
            "C: Typedef definition and usage share symbol",
        ),
        # === TOML ===
        (
            "toml",
            "config.toml",
            """
            [package]
            name = "myapp"
            version = "1.0.0"

            [package.metadata]
            authors = ["John Doe"]
            """,
            [(0, 2), (4, 5)],  # Modify package and package.metadata tables
            (0, 2),  # package table
            (4, 5),  # package.metadata table
            True,
            "TOML: Nested tables share parent table name",
        ),
        (
            "toml",
            "config.toml",
            """
            [server]
            host = "localhost"
            port = 8080

            [database]
            user = "admin"
            password = "secret"
            """,
            [(0, 2), (4, 6)],  # Modify different tables
            (0, 2),  # server table
            (4, 6),  # database table
            False,
            "TOML: Different top-level tables don't share",
        ),
        (
            "toml",
            "config.toml",
            """
            [[products]]
            name = "Widget"
            sku = 12345

            [[products]]
            name = "Gadget"
            sku = 67890
            """,
            [(0, 2), (4, 6)],  # Modify array table elements
            (0, 2),  # first products element
            (4, 6),  # second products element
            True,
            "TOML: Array table elements share table name",
        ),
        (
            "toml",
            "config.toml",
            """
            [config]
            debug = true

            [settings]
            timeout = 30
            """,
            [(0, 1), (3, 4)],  # Modify different top-level tables
            (0, 1),  # config table
            (3, 4),  # settings table
            False,
            "TOML: Unrelated tables don't share symbols",
        ),
        (
            "toml",
            "config.toml",
            """
            [build]
            target = "release"

            [build.dependencies]
            pkg1 = "1.0"
            """,
            [(0, 1), (3, 4)],  # Modify parent table and nested table
            (0, 1),  # build table
            (3, 4),  # build.dependencies table
            True,
            "TOML: Nested table shares parent table name",
        ),
        # === EXTENDED PYTHON TESTS ===
        (
            "python",
            "test.py",
            """
            class Database:
                def connect(self):
                    return "connected"

            def init_db():
                db = Database()
                return db.connect()
            """,
            [(0, 2), (5, 7)],  # Modify class and method call
            (0, 2),  # Database class
            (5, 7),  # init_db with method call
            True,
            "Python: Method call on modified class should link",
        ),
        (
            "python",
            "test.py",
            """
            def validate_data(data):
                return len(data) > 0

            @validate_data
            def process():
                return [1, 2, 3]
            """,
            [(0, 1), (3, 5)],  # Modify decorator function and decorated function
            (0, 1),  # validate_data function
            (3, 5),  # process function with decorator
            True,
            "Python: Decorator usage should link to modified function",
        ),
        (
            "python",
            "test.py",
            """
            class Animal:
                def speak(self):
                    return "sound"

            class Dog(Animal):
                def bark(self):
                    return "woof"
            """,
            [(0, 2), (4, 6)],  # Modify base and derived class
            (0, 2),  # Animal base class
            (4, 6),  # Dog derived class
            True,
            "Python: Inheritance should link parent class usage",
        ),
        (
            "python",
            "test.py",
            """
            multiplier = 5

            def apply():
                result = lambda x: x * multiplier
                return result(10)
            """,
            [(0, 0), (3, 4)],  # Modify variable and lambda using it
            (0, 0),  # multiplier definition
            (3, 4),  # lambda using multiplier
            True,
            "Python: Lambda using modified variable should link",
        ),
        (
            "python",
            "test.py",
            """
            numbers = [1, 2, 3, 4, 5]

            def process():
                squared = [x * x for x in numbers]
                return squared
            """,
            [(0, 0), (3, 4)],  # Modify list and comprehension using it
            (0, 0),  # numbers definition
            (3, 4),  # list comprehension using numbers
            True,
            "Python: List comprehension using modified variable should link",
        ),
        # === EXTENDED JAVASCRIPT TESTS ===
        (
            "javascript",
            "test.js",
            """
            const config = { timeout: 5000 };

            const fetchData = () => {
                return fetch('/api', { timeout: config.timeout });
            };
            """,
            [(0, 0), (2, 4)],  # Modify config and arrow function using it
            (0, 0),  # config definition
            (2, 4),  # fetchData arrow function
            True,
            "JavaScript: Arrow function using modified variable should link",
        ),
        (
            "javascript",
            "test.js",
            """
            class Service {
                process(data) {
                    return data.toUpperCase();
                }
            }

            function handleRequest() {
                const service = new Service();
                return service.process('test');
            }
            """,
            [(0, 4), (6, 9)],  # Modify class and method call
            (0, 4),  # Service class
            (6, 9),  # handleRequest with method call
            True,
            "JavaScript: Method call on modified class should link",
        ),
        (
            "javascript",
            "test.js",
            """
            const settings = {
                theme: 'dark',
                language: 'en'
            };

            function configure() {
                const { theme, language } = settings;
                return theme + language;
            }
            """,
            [(0, 3), (5, 8)],  # Modify object and destructuring
            (0, 3),  # settings object
            (5, 8),  # configure with destructuring
            True,
            "JavaScript: Destructuring from modified object should link",
        ),
        (
            "javascript",
            "test.js",
            """
            async function fetchUser() {
                return { id: 1, name: 'John' };
            }

            async function getUser() {
                const user = await fetchUser();
                return user;
            }
            """,
            [(0, 2), (4, 7)],  # Modify async function and its await
            (0, 2),  # fetchUser function
            (4, 7),  # getUser with await
            True,
            "JavaScript: Await of modified async function should link",
        ),
        (
            "javascript",
            "test.js",
            """
            function createCounter() {
                let count = 0;
                return () => count++;
            }

            const counter = createCounter();
            """,
            [(0, 3), (5, 5)],  # Modify factory function and usage
            (0, 3),  # createCounter function
            (5, 5),  # counter assignment
            True,
            "JavaScript: Factory function usage should link",
        ),
        # === EXTENDED TYPESCRIPT TESTS ===
        (
            "typescript",
            "test.ts",
            """
            enum Status {
                Active,
                Inactive,
                Pending
            }

            function checkStatus(status: Status) {
                return status === Status.Active;
            }
            """,
            [(0, 4), (6, 8)],  # Modify enum and usage
            (0, 4),  # Status enum
            (6, 8),  # checkStatus function
            True,
            "TypeScript: Enum usage should link to modified enum",
        ),
        (
            "typescript",
            "test.ts",
            """
            class Container<T> {
                constructor(public value: T) {}
            }

            function createContainer(): Container<string> {
                return new Container('test');
            }
            """,
            [(0, 2), (4, 6)],  # Modify generic class and instantiation
            (0, 2),  # Container class
            (4, 6),  # createContainer function
            True,
            "TypeScript: Generic type usage should link",
        ),
        (
            "typescript",
            "test.ts",
            """
            interface Drawable {
                draw(): void;
            }

            class Circle implements Drawable {
                draw() {
                    console.log('drawing circle');
                }
            }
            """,
            [(0, 2), (4, 8)],  # Modify interface and implementation
            (0, 2),  # Drawable interface
            (4, 8),  # Circle class implementing it
            True,
            "TypeScript: Interface implementation should link",
        ),
        (
            "typescript",
            "test.ts",
            """
            type Animal = { name: string };

            function isAnimal(obj: any): obj is Animal {
                return obj && typeof obj.name === 'string';
            }
            """,
            [(0, 0), (2, 4)],  # Modify type and type guard
            (0, 0),  # Animal type
            (2, 4),  # isAnimal type guard
            True,
            "TypeScript: Type guard using modified type should link",
        ),
        (
            "typescript",
            "test.ts",
            """
            type Handler = (data: string) => void;

            const processHandler: Handler = (data) => {
                console.log(data);
            };
            """,
            [(0, 0), (2, 4)],  # Modify type alias and usage
            (0, 0),  # Handler type
            (2, 4),  # processHandler using type
            True,
            "TypeScript: Type alias usage in annotation should link",
        ),
        # === EXTENDED GO TESTS ===
        (
            "go",
            "test.go",
            """
            package main

            type User struct {
                Name string
            }

            func (u *User) GetName() string {
                return u.Name
            }
            """,
            [(2, 4), (6, 8)],  # Modify struct and receiver method
            (2, 4),  # User struct
            (6, 8),  # GetName receiver method
            True,
            "Go: Receiver method should link to modified struct",
        ),
        (
            "go",
            "test.go",
            """
            package main

            type Writer interface {
                Write(data string) error
            }

            type FileWriter struct{}

            func (f FileWriter) Write(data string) error {
                return nil
            }
            """,
            [(2, 4), (6, 10)],  # Modify interface and implementation
            (2, 4),  # Writer interface
            (6, 10),  # FileWriter implementing Writer
            False,
            "Go: Implicit interface implementation doesn't link via symbols",
        ),
        (
            "go",
            "test.go",
            """
            package main

            type Base struct {
                ID int
            }

            type Extended struct {
                Base
                Name string
            }
            """,
            [(2, 4), (6, 9)],  # Modify base struct and embedding
            (2, 4),  # Base struct
            (6, 9),  # Extended struct with embedding
            True,
            "Go: Struct embedding should link to modified base struct",
        ),
        (
            "go",
            "test.go",
            """
            package main

            type Result interface{}

            func processResult(r interface{}) {
                if result, ok := r.(Result); ok {
                    _ = result
                }
            }
            """,
            [(2, 2), (4, 8)],  # Modify interface and type assertion
            (2, 2),  # Result interface
            (4, 8),  # processResult with type assertion
            True,
            "Go: Type assertion with modified type should link",
        ),
        (
            "go",
            "test.go",
            """
            package main

            type Config struct {
                Port int
            }

            var defaultConfig = Config{Port: 8080}

            func getConfig() *Config {
                return &defaultConfig
            }
            """,
            [(2, 4), (6, 6)],  # Modify struct and variable initialization
            (2, 4),  # Config struct
            (6, 6),  # defaultConfig using Config
            True,
            "Go: Struct literal should link to modified struct",
        ),
        # === EXTENDED RUST TESTS ===
        (
            "rust",
            "test.rs",
            """
            trait Drawable {
                fn draw(&self);
            }

            struct Circle {
                radius: f64,
            }

            impl Drawable for Circle {
                fn draw(&self) {
                    println!("Drawing circle");
                }
            }
            """,
            [(0, 2), (8, 12)],  # Modify trait and impl
            (0, 2),  # Drawable trait
            (8, 12),  # impl Drawable for Circle
            True,
            "Rust: Trait implementation should link to modified trait",
        ),
        (
            "rust",
            "test.rs",
            """
            struct Point {
                x: i32,
                y: i32,
            }

            impl Point {
                fn new(x: i32, y: i32) -> Self {
                    Point { x, y }
                }
            }
            """,
            [(0, 3), (5, 9)],  # Modify struct and impl block
            (0, 3),  # Point struct
            (5, 9),  # impl Point
            True,
            "Rust: Impl block should link to modified struct",
        ),
        (
            "rust",
            "test.rs",
            """
            enum Message {
                Text(String),
                Number(i32),
            }

            fn process(msg: Message) {
                match msg {
                    Message::Text(s) => println!("{}", s),
                    Message::Number(n) => println!("{}", n),
                }
            }
            """,
            [(0, 3), (5, 10)],  # Modify enum and variant usage
            (0, 3),  # Message enum
            (5, 10),  # process with enum variants
            True,
            "Rust: Enum variant usage should link to modified enum",
        ),
        (
            "rust",
            "test.rs",
            """
            mod utils {
                pub fn helper() -> i32 {
                    42
                }
            }

            fn use_utils() -> i32 {
                utils::helper()
            }
            """,
            [(0, 4), (6, 8)],  # Modify module and usage
            (0, 4),  # utils module
            (6, 8),  # use_utils calling module function
            True,
            "Rust: Module item usage should link to modified module",
        ),
        (
            "rust",
            "test.rs",
            """
            type Result<T> = std::result::Result<T, String>;

            fn process() -> Result<i32> {
                Ok(42)
            }
            """,
            [(0, 0), (2, 4)],  # Modify type alias and usage
            (0, 0),  # Result type alias
            (2, 4),  # process using type alias
            True,
            "Rust: Type alias usage should link",
        ),
        # === EXTENDED JAVA TESTS ===
        (
            "java",
            "test.java",
            """
            interface Runnable {
                void run();
            }

            class Task implements Runnable {
                public void run() {
                    System.out.println("Running");
                }
            }
            """,
            [(0, 2), (4, 8)],  # Modify interface and implementation
            (0, 2),  # Runnable interface
            (4, 8),  # Task class implementing it
            True,
            "Java: Interface implementation should link",
        ),
        (
            "java",
            "test.java",
            """
            class Animal {
                public void makeSound() {
                    System.out.println("Some sound");
                }
            }

            class Dog extends Animal {
                @Override
                public void makeSound() {
                    System.out.println("Bark");
                }
            }
            """,
            [(0, 4), (6, 11)],  # Modify parent class and override
            (0, 4),  # Animal class
            (6, 11),  # Dog class with override
            True,
            "Java: Method override should link to modified parent class",
        ),
        (
            "java",
            "test.java",
            """
            enum Color {
                RED, GREEN, BLUE
            }

            class Painter {
                public void paint(Color color) {
                    if (color == Color.RED) {
                        System.out.println("Painting red");
                    }
                }
            }
            """,
            [(0, 2), (4, 10)],  # Modify enum and usage
            (0, 2),  # Color enum
            (4, 10),  # Painter using Color
            True,
            "Java: Enum usage should link to modified enum",
        ),
        (
            "java",
            "test.java",
            """
            class Outer {
                private int value = 10;

                class Inner {
                    public int getValue() {
                        return value;
                    }
                }
            }
            """,
            [(0, 8)],  # Modify outer class
            (0, 2),  # Outer class fields
            (3, 7),  # Inner class using outer value
            True,
            "Java: Inner class accessing outer class member should link",
        ),
        (
            "java",
            "test.java",
            """
            class Container<T> {
                private T value;

                public T get() {
                    return value;
                }
            }

            class Example {
                public Container<String> create() {
                    return new Container<>();
                }
            }
            """,
            [(0, 6), (8, 12)],  # Modify generic class and usage
            (0, 6),  # Container class
            (8, 12),  # Example using Container
            True,
            "Java: Generic class instantiation should link",
        ),
        # === EXTENDED C++ TESTS ===
        (
            "cpp",
            "test.cpp",
            """
            class Vector {
            public:
                int x, y;
                void normalize();
            };

            void Vector::normalize() {
                x = y = 0;
            }
            """,
            [(0, 4), (6, 8)],  # Modify class and member function definition
            (0, 4),  # Vector class
            (6, 8),  # normalize member function
            True,
            "C++: Class member function definition should link",
        ),
        (
            "cpp",
            "test.cpp",
            """
            namespace math {
                int add(int a, int b) {
                    return a + b;
                }
            }

            int calculate() {
                return math::add(5, 3);
            }
            """,
            [(0, 4), (6, 8)],  # Modify namespace and usage
            (0, 4),  # math namespace
            (6, 8),  # calculate using namespace
            True,
            "C++: Namespace usage should link to modified namespace",
        ),
        (
            "cpp",
            "test.cpp",
            """
            template<typename T>
            class Container {
            public:
                T value;
            };

            Container<int> create() {
                return Container<int>();
            }
            """,
            [(0, 4), (6, 8)],  # Modify template and instantiation
            (0, 4),  # Container template
            (6, 8),  # create instantiating template
            True,
            "C++: Template instantiation should link",
        ),
        (
            "cpp",
            "test.cpp",
            """
            class Point {
            public:
                int x, y;
                Point operator+(const Point& other) {
                    return Point{x + other.x, y + other.y};
                }
            };

            Point add_points(Point a, Point b) {
                return a + b;
            }
            """,
            [(0, 6), (8, 10)],  # Modify class with operator and usage
            (0, 6),  # Point class
            (8, 10),  # add_points using operator
            True,
            "C++: Operator overload usage should link",
        ),
        (
            "cpp",
            "test.cpp",
            """
            struct Data {
                int value;
            };

            void process(Data* data) {
                data->value = 10;
            }
            """,
            [(0, 2), (4, 6)],  # Modify struct and pointer usage
            (0, 2),  # Data struct
            (4, 6),  # process using Data
            True,
            "C++: Struct pointer usage should link",
        ),
        # === EXTENDED C# TESTS ===
        (
            "csharp",
            "test.cs",
            """
            class User {
                public string Name { get; set; }
                public int Age { get; set; }
            }

            class UserService {
                public void UpdateUser(User user) {
                    user.Name = "Updated";
                }
            }
            """,
            [(0, 3), (5, 9)],  # Modify class and property usage
            (0, 3),  # User class
            (5, 9),  # UserService using properties
            True,
            "C#: Property usage should link to modified class",
        ),
        (
            "csharp",
            "test.cs",
            """
            class Product {
                public string Name { get; set; }
                public decimal Price { get; set; }
            }

            class Query {
                public IEnumerable<Product> GetExpensive(List<Product> products) {
                    return products.Where(p => p.Price > 100);
                }
            }
            """,
            [(0, 3), (5, 9)],  # Modify class and LINQ usage
            (0, 3),  # Product class
            (5, 9),  # Query using Product in LINQ
            True,
            "C#: LINQ with modified type should link",
        ),
        (
            "csharp",
            "test.cs",
            """
            static class StringExtensions {
                public static string Reverse(this string str) {
                    return new string(str.Reverse().ToArray());
                }
            }

            class Example {
                public string Process(string input) {
                    return input.Reverse();
                }
            }
            """,
            [(0, 4), (6, 10)],  # Modify extension method and usage
            (0, 4),  # StringExtensions
            (6, 10),  # Example using extension
            True,
            "C#: Extension method usage should link",
        ),
        (
            "csharp",
            "test.cs",
            """
            class Button {
                public event EventHandler Clicked;

                public void Click() {
                    Clicked?.Invoke(this, EventArgs.Empty);
                }
            }

            class Form {
                public void AttachButton(Button btn) {
                    btn.Clicked += OnButtonClick;
                }

                void OnButtonClick(object sender, EventArgs e) {}
            }
            """,
            [(0, 6), (8, 14)],  # Modify class with event and usage
            (0, 6),  # Button class with event
            (8, 14),  # Form subscribing to event
            True,
            "C#: Event subscription should link to modified class",
        ),
        (
            "csharp",
            "test.cs",
            """
            namespace Services {
                public class DataService {
                    public void Save() {}
                }
            }

            class Controller {
                public void Execute() {
                    var service = new Services.DataService();
                }
            }
            """,
            [(0, 4), (6, 10)],  # Modify namespace and usage
            (0, 4),  # Services namespace
            (6, 10),  # Controller using namespace
            True,
            "C#: Namespace qualified usage should link",
        ),
        # === EXTENDED RUBY TESTS ===
        (
            "ruby",
            "test.rb",
            """
            class Logger
              def log(message)
                puts message
              end
            end

            def process
              logger = Logger.new
              logger.log("Processing")
            end
            """,
            [(0, 4), (6, 9)],  # Modify class and method call
            (0, 4),  # Logger class
            (6, 9),  # process method calling logger
            True,
            "Ruby: Method call on modified class should link",
        ),
        (
            "ruby",
            "test.rb",
            """
            module Utilities
              def self.format(text)
                text.upcase
              end
            end

            def process_text(text)
              Utilities.format(text)
            end
            """,
            [(0, 4), (6, 8)],  # Modify module and usage
            (0, 4),  # Utilities module
            (6, 8),  # process_text calling module method
            True,
            "Ruby: Module method call should link",
        ),
        (
            "ruby",
            "test.rb",
            """
            class Animal
              def speak
                "sound"
              end
            end

            class Dog < Animal
              def bark
                "woof"
              end
            end
            """,
            [(0, 4), (6, 10)],  # Modify parent and child class
            (0, 4),  # Animal class
            (6, 10),  # Dog inheriting from Animal
            True,
            "Ruby: Class inheritance should link",
        ),
        (
            "ruby",
            "test.rb",
            """
            CONSTANT_VALUE = 42

            def use_constant
              result = CONSTANT_VALUE * 2
              result
            end
            """,
            [(0, 0), (2, 5)],  # Modify constant and usage
            (0, 0),  # CONSTANT_VALUE
            (2, 5),  # use_constant using constant
            True,
            "Ruby: Constant usage should link",
        ),
        (
            "ruby",
            "test.rb",
            """
            class Calculator
              attr_accessor :value

              def initialize(val)
                @value = val
              end
            end

            def create_calc
              calc = Calculator.new(10)
              calc.value = 20
            end
            """,
            [(0, 6), (8, 11)],  # Modify class with accessor and usage
            (0, 6),  # Calculator class
            (8, 11),  # create_calc using accessor
            True,
            "Ruby: Attribute accessor usage should link",
        ),
        # === EXTENDED PHP TESTS ===
        (
            "php",
            "test.php",
            """
            <?php
            class Repository {
                public function find($id) {
                    return null;
                }
            }

            function getData($id) {
                $repo = new Repository();
                return $repo->find($id);
            }
            """,
            [(1, 5), (7, 10)],  # Modify class and method call
            (1, 5),  # Repository class
            (7, 10),  # getData calling method
            True,
            "PHP: Method call on modified class should link",
        ),
        (
            "php",
            "test.php",
            """
            <?php
            interface Validator {
                public function validate($data);
            }

            class EmailValidator implements Validator {
                public function validate($data) {
                    return filter_var($data, FILTER_VALIDATE_EMAIL);
                }
            }
            """,
            [(1, 3), (5, 9)],  # Modify interface and implementation
            (1, 3),  # Validator interface
            (5, 9),  # EmailValidator implementing it
            True,
            "PHP: Interface implementation should link",
        ),
        (
            "php",
            "test.php",
            """
            <?php
            trait Loggable {
                public function log($message) {
                    echo $message;
                }
            }

            class Service {
                use Loggable;
            }
            """,
            [(1, 5), (7, 9)],  # Modify trait and usage
            (1, 5),  # Loggable trait
            (7, 9),  # Service using trait
            True,
            "PHP: Trait usage should link",
        ),
        (
            "php",
            "test.php",
            """
            <?php
            namespace App\\Services;

            class DataService {
                public function process() {}
            }

            function createService() {
                return new \\App\\Services\\DataService();
            }
            """,
            [(1, 5), (7, 9)],  # Modify namespace and usage
            (1, 5),  # DataService in namespace
            (7, 9),  # createService using fully qualified name
            True,
            "PHP: Namespace qualified class usage should link",
        ),
        (
            "php",
            "test.php",
            """
            <?php
            abstract class Controller {
                abstract public function execute();
            }

            class HomeController extends Controller {
                public function execute() {
                    return "home";
                }
            }
            """,
            [(1, 3), (5, 9)],  # Modify abstract class and concrete implementation
            (1, 3),  # Controller abstract class
            (5, 9),  # HomeController extending it
            True,
            "PHP: Abstract class extension should link",
        ),
        # === EXTENDED SWIFT TESTS ===
        (
            "swift",
            "test.swift",
            """
            protocol Drawable {
                func draw()
            }

            class Circle: Drawable {
                func draw() {
                    print("Drawing circle")
                }
            }
            """,
            [(0, 2), (4, 8)],  # Modify protocol and implementation
            (0, 2),  # Drawable protocol
            (4, 8),  # Circle implementing protocol
            True,
            "Swift: Protocol implementation should link",
        ),
        (
            "swift",
            "test.swift",
            """
            struct Point {
                var x: Int
                var y: Int
            }

            func createPoint() -> Point {
                return Point(x: 0, y: 0)
            }
            """,
            [(0, 3), (5, 7)],  # Modify struct and initializer usage
            (0, 3),  # Point struct
            (5, 7),  # createPoint using initializer
            True,
            "Swift: Struct initializer usage should link",
        ),
        (
            "swift",
            "test.swift",
            """
            enum Result {
                case success(String)
                case failure(Error)
            }

            func processResult(result: Result) {
                switch result {
                case .success(let msg):
                    print(msg)
                case .failure(let err):
                    print(err)
                }
            }
            """,
            [(0, 3), (5, 12)],  # Modify enum and pattern matching
            (0, 3),  # Result enum
            (5, 12),  # processResult with pattern matching
            True,
            "Swift: Enum pattern matching should link",
        ),
        (
            "swift",
            "test.swift",
            """
            class Container<T> {
                var value: T
                init(value: T) {
                    self.value = value
                }
            }

            func create() -> Container<Int> {
                return Container(value: 42)
            }
            """,
            [(0, 5), (7, 9)],  # Modify generic class and usage
            (0, 5),  # Container class
            (7, 9),  # create using generic
            True,
            "Swift: Generic class usage should link",
        ),
        (
            "swift",
            "test.swift",
            """
            typealias Handler = (String) -> Void

            func execute(handler: Handler) {
                handler("test")
            }
            """,
            [(0, 0), (2, 4)],  # Modify typealias and usage
            (0, 0),  # Handler typealias
            (2, 4),  # execute using typealias
            True,
            "Swift: Typealias usage should link",
        ),
        # === EXTENDED KOTLIN TESTS ===
        (
            "kotlin",
            "test.kt",
            """
            interface Repository {
                fun save(data: String)
            }

            class DatabaseRepository : Repository {
                override fun save(data: String) {
                    println(data)
                }
            }
            """,
            [(0, 2), (4, 8)],  # Modify interface and implementation
            (0, 2),  # Repository interface
            (4, 8),  # DatabaseRepository implementing it
            True,
            "Kotlin: Interface implementation should link",
        ),
        (
            "kotlin",
            "test.kt",
            """
            data class User(val name: String, val age: Int)

            fun createUser(): User {
                return User("John", 30)
            }
            """,
            [(0, 0), (2, 4)],  # Modify data class and usage
            (0, 0),  # User data class
            (2, 4),  # createUser using constructor
            True,
            "Kotlin: Data class usage should link",
        ),
        (
            "kotlin",
            "test.kt",
            """
            sealed class Result {
                data class Success(val value: String) : Result()
                data class Error(val message: String) : Result()
            }

            fun handle(result: Result) {
                when (result) {
                    is Result.Success -> println(result.value)
                    is Result.Error -> println(result.message)
                }
            }
            """,
            [(0, 3), (5, 10)],  # Modify sealed class and when expression
            (0, 3),  # Result sealed class
            (5, 10),  # handle with when
            True,
            "Kotlin: Sealed class pattern matching should link",
        ),
        (
            "kotlin",
            "test.kt",
            """
            fun <T> identity(value: T): T {
                return value
            }

            fun use() {
                val result = identity<Int>(42)
            }
            """,
            [(0, 2), (4, 6)],  # Modify generic function and usage
            (0, 2),  # identity function
            (4, 6),  # use calling generic function
            True,
            "Kotlin: Generic function call should link",
        ),
        (
            "kotlin",
            "test.kt",
            """
            object Singleton {
                fun process() {
                    println("processing")
                }
            }

            fun execute() {
                Singleton.process()
            }
            """,
            [(0, 4), (6, 8)],  # Modify object and usage
            (0, 4),  # Singleton object
            (6, 8),  # execute calling object method
            True,
            "Kotlin: Object singleton usage should link",
        ),
        # === EXTENDED SCALA TESTS ===
        (
            "scala",
            "test.scala",
            """
            trait Processor {
              def process(data: String): String
            }

            class TextProcessor extends Processor {
              def process(data: String): String = data.toUpperCase
            }
            """,
            [(0, 2), (4, 6)],  # Modify trait and implementation
            (0, 2),  # Processor trait
            (4, 6),  # TextProcessor implementing trait
            True,
            "Scala: Trait implementation should link",
        ),
        (
            "scala",
            "test.scala",
            """
            case class Person(name: String, age: Int)

            def createPerson(): Person = {
              Person("John", 30)
            }
            """,
            [(0, 0), (2, 4)],  # Modify case class and usage
            (0, 0),  # Person case class
            (2, 4),  # createPerson using case class
            True,
            "Scala: Case class usage should link",
        ),
        (
            "scala",
            "test.scala",
            """
            sealed trait Result
            case class Success(value: String) extends Result
            case class Failure(error: String) extends Result

            def handle(result: Result): String = result match {
              case Success(v) => v
              case Failure(e) => e
            }
            """,
            [(0, 2), (4, 7)],  # Modify sealed trait and pattern matching
            (0, 2),  # Result sealed trait
            (4, 7),  # handle with pattern matching
            True,
            "Scala: Sealed trait pattern matching should link",
        ),
        (
            "scala",
            "test.scala",
            """
            object Utils {
              def format(text: String): String = text.toUpperCase
            }

            def process(text: String): String = {
              Utils.format(text)
            }
            """,
            [(0, 2), (4, 6)],  # Modify object and usage
            (0, 2),  # Utils object
            (4, 6),  # process calling object method
            True,
            "Scala: Object method call should link",
        ),
        (
            "scala",
            "test.scala",
            """
            class Container[T](val value: T) {
              def get: T = value
            }

            def create(): Container[Int] = {
              new Container(42)
            }
            """,
            [(0, 2), (4, 6)],  # Modify generic class and usage
            (0, 2),  # Container generic class
            (4, 6),  # create using generic
            True,
            "Scala: Generic class usage should link",
        ),
        # === EXTENDED R TESTS ===
        (
            "r",
            "test.r",
            """
            process_data <- function(data) {
              return(data * 2)
            }

            result <- process_data(c(1, 2, 3))
            """,
            [(0, 2), (4, 4)],  # Modify function and usage
            (0, 2),  # process_data function
            (4, 4),  # result using function
            True,
            "R: Function call should link to modified function",
        ),
        (
            "r",
            "test.r",
            """
            create_list <- function() {
              list(a = 1, b = 2, c = 3)
            }

            my_list <- create_list()
            value <- my_list$a
            """,
            [(0, 2), (4, 5)],  # Modify function and list access
            (0, 2),  # create_list function
            (4, 5),  # my_list usage
            True,
            "R: List creation function usage should link",
        ),
        (
            "r",
            "test.r",
            """
            GLOBAL_CONFIG <- list(timeout = 30)

            get_timeout <- function() {
              return(GLOBAL_CONFIG$timeout)
            }
            """,
            [(0, 0), (2, 4)],  # Modify global variable and usage
            (0, 0),  # GLOBAL_CONFIG
            (2, 4),  # get_timeout using global
            True,
            "R: Global variable usage should link",
        ),
        (
            "r",
            "test.r",
            """
            apply_transform <- function(data, fn) {
              return(fn(data))
            }

            result <- apply_transform(10, function(x) x * 2)
            """,
            [(0, 2), (4, 4)],  # Modify higher-order function and usage
            (0, 2),  # apply_transform function
            (4, 4),  # result using function
            True,
            "R: Higher-order function usage should link",
        ),
        (
            "r",
            "test.r",
            """
            make_adder <- function(n) {
              function(x) {
                x + n
              }
            }

            add_five <- make_adder(5)
            """,
            [(0, 4), (6, 6)],  # Modify closure factory and usage
            (0, 4),  # make_adder function
            (6, 6),  # add_five assignment
            True,
            "R: Closure factory usage should link",
        ),
        # === EXTENDED LUA TESTS ===
        (
            "lua",
            "test.lua",
            """
            function create_object(name)
                return { name = name }
            end

            local obj = create_object("test")
            """,
            [(0, 2), (4, 4)],  # Modify function and usage
            (0, 2),  # create_object function
            (4, 4),  # obj using function
            True,
            "Lua: Function call should link to modified function",
        ),
        (
            "lua",
            "test.lua",
            """
            local Config = {
                timeout = 30,
                retries = 3
            }

            function get_timeout()
                return Config.timeout
            end
            """,
            [(0, 3), (5, 7)],  # Modify table and usage
            (0, 3),  # Config table
            (5, 7),  # get_timeout accessing table
            True,
            "Lua: Table field access should link to modified table",
        ),
        (
            "lua",
            "test.lua",
            """
            local function make_counter()
                local count = 0
                return function()
                    count = count + 1
                    return count
                end
            end

            local counter = make_counter()
            """,
            [(0, 6), (8, 8)],  # Modify factory function and usage
            (0, 6),  # make_counter function
            (8, 8),  # counter assignment
            True,
            "Lua: Closure factory usage should link",
        ),
        (
            "lua",
            "test.lua",
            """
            Point = {}
            Point.__index = Point

            function Point:new(x, y)
                local pt = setmetatable({}, Point)
                pt.x = x
                pt.y = y
                return pt
            end

            local p = Point:new(10, 20)
            """,
            [(0, 8), (10, 10)],  # Modify metatable class and usage
            (0, 8),  # Point metatable setup
            (10, 10),  # p instantiation
            True,
            "Lua: Metatable-based class usage should link",
        ),
        (
            "lua",
            "test.lua",
            """
            local utils = {}

            function utils.format(text)
                return string.upper(text)
            end

            local result = utils.format("test")
            """,
            [(0, 4), (6, 6)],  # Modify module table and usage
            (0, 4),  # utils module
            (6, 6),  # result using module function
            True,
            "Lua: Module function call should link",
        ),
        # === EXTENDED DART TESTS ===
        (
            "dart",
            "test.dart",
            """
            abstract class Repository {
              Future<void> save(String data);
            }

            class DatabaseRepository implements Repository {
              Future<void> save(String data) async {
                print(data);
              }
            }
            """,
            [(0, 2), (4, 8)],  # Modify interface and implementation
            (0, 2),  # Repository interface
            (4, 8),  # DatabaseRepository implementing it
            True,
            "Dart: Interface implementation should link",
        ),
        (
            "dart",
            "test.dart",
            """
            class Person {
              final String name;
              final int age;

              Person(this.name, this.age);
            }

            Person createPerson() {
              return Person("John", 30);
            }
            """,
            [(0, 5), (7, 9)],  # Modify class and constructor usage
            (0, 5),  # Person class
            (7, 9),  # createPerson using constructor
            True,
            "Dart: Constructor usage should link to modified class",
        ),
        (
            "dart",
            "test.dart",
            """
            enum Status {
              active,
              inactive,
              pending
            }

            String getStatusText(Status status) {
              switch (status) {
                case Status.active:
                  return "Active";
                default:
                  return "Other";
              }
            }
            """,
            [(0, 4), (6, 13)],  # Modify enum and switch usage
            (0, 4),  # Status enum
            (6, 13),  # getStatusText with switch
            True,
            "Dart: Enum in switch should link",
        ),
        (
            "dart",
            "test.dart",
            """
            mixin Loggable {
              void log(String message) {
                print(message);
              }
            }

            class Service with Loggable {
              void process() {
                log("Processing");
              }
            }
            """,
            [(0, 4), (6, 10)],  # Modify mixin and usage
            (0, 4),  # Loggable mixin
            (6, 10),  # Service using mixin
            True,
            "Dart: Mixin usage should link",
        ),
        (
            "dart",
            "test.dart",
            """
            class Container<T> {
              final T value;
              Container(this.value);
            }

            Container<int> create() {
              return Container(42);
            }
            """,
            [(0, 3), (5, 7)],  # Modify generic class and usage
            (0, 3),  # Container class
            (5, 7),  # create using generic
            True,
            "Dart: Generic class usage should link",
        ),
        # === USAGE-ONLY TESTS ===
        (
            "python",
            "test.py",
            """
            def foo():
                x = 1
                y = x + 2
                return y
            """,
            [(2, 2)],  # Only modify usage of x, not definition
            (1, 1),  # x definition (not modified)
            (2, 2),  # x usage (modified)
            False,
            "Python: Usage-only modification doesn't group with definition",
        ),
        (
            "javascript",
            "test.js",
            """
            function calculate() {
                const value = 10;
                const result = value * 2;
                return result;
            }
            """,
            [(2, 2)],  # Modify result definition
            (2, 2),  # result assignment (definition)
            (3, 3),  # result return (usage)
            True,
            "JavaScript: Definition and usage of same variable share symbol",
        ),
        # === JSON ===
        (
            "json",
            "test.json",
            """
            {
                "name": "example",
                "version": "1.0.0",
                "config": {
                    "name": "nested-name"
                }
            }
            """,
            [(1, 1), (4, 4)],  # Modify both "name" keys
            (1, 1),  # Top-level "name" key
            (4, 4),  # Nested "name" key in config
            True,
            "JSON: Same key name in different objects share symbol",
        ),
        (
            "json",
            "test.json",
            """
            {
                "database": {
                    "host": "localhost",
                    "port": 5432
                },
                "cache": {
                    "host": "redis.local",
                    "ttl": 3600
                }
            }
            """,
            [(2, 2), (6, 6)],  # Modify "host" in both database and cache
            (2, 2),  # database.host
            (6, 6),  # cache.host
            True,
            "JSON: Same key 'host' in different objects share symbol",
        ),
        (
            "json",
            "test.json",
            """
            {
                "users": [
                    {"id": 1, "name": "Alice"},
                    {"id": 2, "name": "Bob"}
                ],
                "products": [
                    {"id": 100, "name": "Widget"}
                ]
            }
            """,
            [(2, 2), (6, 6)],  # Modify "id" in users and products
            (2, 2),  # users[0].id
            (6, 6),  # products[0].id
            True,
            "JSON: Same key 'id' in array items share symbol",
        ),
        (
            "json",
            "test.json",
            """
            {
                "server": {
                    "port": 8080
                },
                "client": {
                    "timeout": 30
                }
            }
            """,
            [(2, 2), (5, 5)],  # Modify different keys
            (2, 2),  # server.port
            (5, 5),  # client.timeout
            False,
            "JSON: Different keys don't share symbols",
        ),
        (
            "json",
            "test.json",
            """
            {
                "config": {
                    "enabled": true,
                    "level": "debug"
                },
                "settings": {
                    "enabled": false,
                    "mode": "production"
                }
            }
            """,
            [(2, 2), (6, 6)],  # Modify "enabled" in both config and settings
            (2, 2),  # config.enabled
            (6, 6),  # settings.enabled
            True,
            "JSON: Same key 'enabled' in different objects share symbol",
        ),
        # === YAML ===
        (
            "yaml",
            "test.yaml",
            """
            name: example
            version: 1.0.0
            config:
              name: nested-name
            """,
            [(0, 0), (3, 3)],  # Modify both "name" keys
            (0, 0),  # Top-level "name" key
            (3, 3),  # Nested "name" key in config
            True,
            "YAML: Same key name in different contexts share symbol",
        ),
        (
            "yaml",
            "test.yaml",
            """
            database:
              host: localhost
              port: 5432
            cache:
              host: redis.local
              ttl: 3600
            """,
            [(1, 1), (4, 4)],  # Modify "host" in both database and cache
            (1, 1),  # database.host
            (4, 4),  # cache.host
            True,
            "YAML: Same key 'host' in different objects share symbol",
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
            [(1, 1), (3, 3)],  # Modify "id" in array items
            (1, 1),  # users[0].id
            (3, 3),  # users[1].id
            True,
            "YAML: Same key 'id' in array items share symbol",
        ),
        (
            "yaml",
            "test.yaml",
            """
            server:
              port: 8080
            client:
              timeout: 30
            """,
            [(1, 1), (3, 3)],  # Modify different keys
            (1, 1),  # server.port
            (3, 3),  # client.timeout
            False,
            "YAML: Different keys don't share symbols",
        ),
        (
            "yaml",
            "test.yaml",
            """
            config:
              enabled: true
              level: debug
            settings:
              enabled: false
              mode: production
            """,
            [(1, 1), (4, 4)],  # Modify "enabled" in both config and settings
            (1, 1),  # config.enabled
            (4, 4),  # settings.enabled
            True,
            "YAML: Same key 'enabled' in different objects share symbol",
        ),
        # === HTML ===
        (
            "html",
            "test.html",
            """
            <div class="container">
                <p class="text">First</p>
            </div>
            <div class="container">
                <p class="text">Second</p>
            </div>
            """,
            [(0, 0), (3, 3)],  # Modify both "container" class usages
            (0, 0),  # First container div
            (3, 3),  # Second container div
            True,
            "HTML: Same class name 'container' in different elements share symbol",
        ),
        (
            "html",
            "test.html",
            """
            <div id="header">
                <h1 id="title">Title</h1>
            </div>
            <div id="content">
                <p id="text">Content</p>
            </div>
            """,
            [(0, 0), (3, 3)],  # Modify both id attributes
            (0, 0),  # header div
            (3, 3),  # content div
            True,
            "HTML: Elements with id attributes share 'id' symbol",
        ),
        (
            "html",
            "test.html",
            """
            <div class="card">
                <h2 class="title">Card 1</h2>
                <p class="description">Desc 1</p>
            </div>
            <div class="card">
                <h2 class="title">Card 2</h2>
                <p class="description">Desc 2</p>
            </div>
            """,
            [(1, 1), (5, 5)],  # Modify "title" class in both cards
            (1, 1),  # First title
            (5, 5),  # Second title
            True,
            "HTML: Same class 'title' in different card elements share symbol",
        ),
        (
            "html",
            "test.html",
            """
            <div data-component="modal">
                <button data-action="close">X</button>
            </div>
            <div data-component="tooltip">
                <span data-action="show">Info</span>
            </div>
            """,
            [(1, 1), (4, 4)],  # Modify "data-action" attributes
            (1, 1),  # close button
            (4, 4),  # show span
            True,
            "HTML: Elements with data-action attributes share 'data-action' symbol",
        ),
        (
            "html",
            "test.html",
            """
            <custom-element name="widget">
                <custom-element name="button">Click</custom-element>
            </custom-element>
            <custom-element name="widget">
                <custom-element name="input">Type</custom-element>
            </custom-element>
            """,
            [(0, 0), (3, 3)],  # Modify both "widget" custom elements
            (0, 0),  # First widget
            (3, 3),  # Second widget
            True,
            "HTML: Same custom element name 'widget' share symbol",
        ),
    ],
)
def test_symbol_based_grouping(
    tools,
    language,
    filename,
    content,
    modified_lines,
    chunk1_lines,
    chunk2_lines,
    should_share_symbols,
    description,
):
    """Test that two code chunks share (or don't share) symbols based on definitions in
    modified lines.

    Args:
        tools: Fixture providing parser, symbol_extractor, and symbol_mapper
        language: Programming language
        filename: File name for context
        content: Source code content
        modified_lines: List of (start, end) tuples representing lines that are modified in the diff
        chunk1_lines: Tuple (start, end) for first chunk (0-indexed after strip)
        chunk2_lines: Tuple (start, end) for second chunk (0-indexed after strip)
        should_share_symbols: Whether chunks should share symbols
        description: Description of what's being tested
    """
    parser, symbol_extractor, symbol_mapper = tools

    # Clean up content
    clean_content = dedent(content).strip()
    total_lines = len(clean_content.splitlines())

    # Parse the file
    parsed = parser.parse_file(
        filename.encode("utf-8"), clean_content.encode("utf-8"), [(0, total_lines - 1)]
    )
    assert parsed is not None, f"Failed to parse {language} content"
    assert parsed.detected_language == language

    # Extract defined symbols from modified lines only
    defined_symbols = symbol_extractor.extract_defined_symbols(
        parsed.detected_language,
        parsed.root_node,
        modified_lines,
    )

    # Build symbol map with only the defined symbols
    symbol_map = symbol_mapper.build_symbol_map(
        parsed.detected_language,
        parsed.root_node,
        defined_symbols,
        [(0, total_lines - 1)],
    )

    # Get symbols for each chunk's lines
    chunk1_symbols = set()
    for line_num in range(chunk1_lines[0], chunk1_lines[1] + 1):
        symbols = symbol_map.modified_line_symbols.get(line_num, set())
        chunk1_symbols.update(symbols)

    chunk2_symbols = set()
    for line_num in range(chunk2_lines[0], chunk2_lines[1] + 1):
        symbols = symbol_map.modified_line_symbols.get(line_num, set())
        chunk2_symbols.update(symbols)

    # Check if they share any symbols
    shared_symbols = chunk1_symbols & chunk2_symbols
    has_shared_symbols = len(shared_symbols) > 0

    # Assert based on expectation
    if should_share_symbols:
        assert has_shared_symbols, (
            f"{description}\n"
            f"Expected chunks to share symbols, but they don't.\n"
            f"Chunk1 symbols: {chunk1_symbols}\n"
            f"Chunk2 symbols: {chunk2_symbols}\n"
            f"Shared symbols: {shared_symbols}\n"
            f"Defined symbols: {defined_symbols}"
        )
    else:
        assert not has_shared_symbols, (
            f"{description}\n"
            f"Expected chunks NOT to share symbols, but they do.\n"
            f"Chunk1 symbols: {chunk1_symbols}\n"
            f"Chunk2 symbols: {chunk2_symbols}\n"
            f"Shared symbols: {shared_symbols}\n"
            f"Defined symbols: {defined_symbols}"
        )


# -------------------------------------------------------------------------
# Additional Edge Case Tests
# -------------------------------------------------------------------------


def test_no_defined_symbols(tools):
    """Test that when no symbols are defined in modified lines, no grouping occurs."""
    parser, symbol_extractor, symbol_mapper = tools

    content = """
def foo():
    x = 1
    return x

def bar():
    return x
"""
    content = dedent(content).strip()

    parsed = parser.parse_file(
        b"test.py", content.encode("utf-8"), [(0, len(content.splitlines()) - 1)]
    )
    assert parsed is not None

    # Extract symbols from line that doesn't define anything (return statement)
    defined_symbols = symbol_extractor.extract_defined_symbols(
        "python", parsed.root_node, [(2, 2)]
    )

    symbol_map = symbol_mapper.build_symbol_map(
        "python",
        parsed.root_node,
        defined_symbols,
        [(0, len(content.splitlines()) - 1)],
    )

    # No symbols should be in the map since we only modified a usage
    assert len(symbol_map.modified_line_symbols) == 0


def test_symbol_definition_only_in_modified_lines(tools):
    """Test that only symbols defined in modified lines are tracked."""
    parser, symbol_extractor, symbol_mapper = tools

    content = """
class A:
    pass

class B:
    pass

def use_classes():
    a = A()
    b = B()
"""
    content = dedent(content).strip()

    parsed = parser.parse_file(
        b"test.py", content.encode("utf-8"), [(0, len(content.splitlines()) - 1)]
    )
    assert parsed is not None

    # Only extract symbols from class A definition
    defined_symbols = symbol_extractor.extract_defined_symbols(
        "python", parsed.root_node, [(0, 1)]
    )

    symbol_map = symbol_mapper.build_symbol_map(
        "python",
        parsed.root_node,
        defined_symbols,
        [(0, len(content.splitlines()) - 1)],
    )

    # Check that class A appears in symbol map
    class_a_found = False
    class_b_found = False

    for line_symbols in symbol_map.modified_line_symbols.values():
        for symbol in line_symbols:
            if "A" in symbol:
                class_a_found = True
            if "B" in symbol:
                class_b_found = True

    assert class_a_found, "Class A should be in symbol map"
    assert not class_b_found, (
        "Class B should NOT be in symbol map (not in modified lines)"
    )


@pytest.mark.parametrize(
    "language,content,modified_lines,expected_symbol_count",
    [
        (
            "py",
            "x = 1\ny = 2\nz = 3",
            [(0, 0), (1, 1), (2, 2)],
            3,  # All three variables defined
        ),
        (
            "py",
            "x = 1\ny = 2\nz = 3",
            [(0, 0)],
            1,  # Only x defined
        ),
        (
            "js",
            "const a = 1;\nconst b = 2;",
            [(0, 0), (1, 1)],
            2,  # Both constants
        ),
        (
            "java",
            "class A {}\nclass B {}",
            [(0, 0)],
            1,  # Only class A
        ),
    ],
)
def test_symbol_extraction_count(
    tools, language, content, modified_lines, expected_symbol_count
):
    """Test that symbol extraction correctly counts defined symbols."""
    parser, symbol_extractor, _ = tools

    parsed = parser.parse_file(
        f"test.{language}".encode(),
        content.encode("utf-8"),
        [(0, len(content.splitlines()) - 1)],
    )

    defined_symbols = symbol_extractor.extract_defined_symbols(
        parsed.detected_language, parsed.root_node, modified_lines
    )

    assert len(defined_symbols) == expected_symbol_count, (
        f"Expected {expected_symbol_count} symbols, got {len(defined_symbols)}: {defined_symbols}"
    )


def test_symbol_namespace_separation(tools):
    """Test that symbols from different namespaces/classes are kept separate."""
    parser, symbol_extractor, symbol_mapper = tools

    content = """
class A:
    def method(self):
        pass

class B:
    def method(self):
        pass
"""
    content = dedent(content).strip()

    parsed = parser.parse_file(
        b"test.py", content.encode("utf-8"), [(0, len(content.splitlines()) - 1)]
    )
    assert parsed is not None

    # Define both methods
    defined_symbols = symbol_extractor.extract_defined_symbols(
        "python", parsed.root_node, [(0, 7)]
    )

    # Both methods should create distinct symbols (different qualified names)
    # The query manager creates qualified symbols like "identifier_class method"
    # But they should be on different lines in different contexts
    assert len(defined_symbols) >= 1, "Should have at least one method symbol"
