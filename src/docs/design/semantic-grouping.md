# Semantic Grouping & Tree-Sitter

So, how do we actually "understand" your code? We don't just look at lines of text; we look at the structure behind them. To achieve this, we rely on a powerful tool called **Tree-sitter**.

### The Universal Structure: ASTs
Did you know that 99% of programming languages can be represented by something called an **AST (Abstract Syntax Tree)**? You can think of an AST as a preprocessed, structured map of your code. 

**Tree-sitter** is the handy tool that unifies the generation and analysis of these syntax trees. This is what allows us to do our magic! For pretty much every programming language that uses an AST, there exists a Tree-sitter binding that allows us to analyze that language seamlessly.

### Seeing the Matrix
To visualize this, let's look at how a simple Python function is represented by Tree-sitter.

**The Code:**
```python
def foo():
    print("hello, world")
    
foo()
```

**The Generated AST:**
```text
module [0, 0] - [5, 0]
 function_definition [0, 0] - [1, 22]
   name: identifier [0, 4] - [0, 7]
   parameters: parameters [0, 7] - [0, 9]
   body: block [1, 1] - [1, 22]
     expression_statement [1, 1] - [1, 22]
       call [1, 1] - [1, 22]
         function: identifier [1, 1] - [1, 6]
         arguments: argument_list [1, 6] - [1, 22]
           string [1, 7] - [1, 21]
             string_start [1, 7] - [1, 8]
             string_content [1, 8] - [1, 20]
             string_end [1, 20] - [1, 21]
 expression_statement [3, 0] - [3, 5]
   call [3, 0] - [3, 5]
     function: identifier [3, 0] - [3, 3]
     arguments: argument_list [3, 3] - [3, 5]
```
*Want to see this live? You can play with the [Tree-sitter Playground here](https://tree-sitter.github.io/tree-sitter/7-playground.html).*

As you can see, the structure is extensive. But how do we actually use it?

### The Power of Queries
This is where the **Tree-sitter Query** comes into play. A query is a way of "asking" the AST for nodes in the tree that match a specific pattern.

For example, if I wanted to find all function definitions in Python, the query would look simply like this: 
`((function_definition) @function)`

*For more information about query structure, [check out the docs here](https://tree-sitter.github.io/tree-sitter/using-parsers/queries/1-syntax.html).*

With these queries, we can look for everything we need to perform our semantic grouping. We do this in two specific ways: **Scope** and **Symbols**.

#### 1. Grouping by Scope
If I modify a function, I want to ensure that the code within that scope stays together. If we split a `while` loop or an `if` statement in half, we risk invalid syntax.

Using the query example above (`((function_definition) @function)`), we can find the exact start and end lines of `foo()`. We record that range and use it to group any changes found inside it!

#### 2. Grouping by Symbols (Links)
We also want to group changes based on shared symbols. For example, when I defined `foo` above, I want to link that definition with the usage `foo()` at the bottom of the file.

We use queries for this too, but we have to be smarter about it.
*   **The Identifier Problem:** We can find all "identifiers" (names of things), but we don't want to group things based on common words like `print()` or `range()`, right?
*   **The Solution:** We specifically look for *definitions*. We use queries that target the moment a symbol is defined, such as: `(function_definition name: (identifier) @defined_function_name)`.

By identifying exactly what symbols are being *defined* and changed, we can find everywhere else in the code that specific symbol is *used*, and group those chunks together.

### The "Language Config"
We have to write custom queries for each language because, even though AST generation is unified, the actual node names change from language to language.

We define a `language_config.json` file to map these rules. Here is a snippet of how we define Python:

```json
{
    "python": {
        "shared_token_queries": {
            "identifier_class": {
                "general_queries":[
                    "((identifier) @placeholder)"
                ],
                "definition_queries": [
                    "(assignment left: (identifier) @placeholder)",
                    "(class_definition name: (identifier) @placeholder)",
                    "(function_definition name: (identifier) @placeholder)"
                ]
            }
        },
        "scope_queries": [
                "((function_definition) @placeholder)",
                "((decorated_definition) @placeholder)",
                "((while_statement) @placeholder)",
                "((class_definition) @placeholder)",
                "((if_statement) @placeholder)"
            ],
        "share_tokens_between_files": "True"
    }
    ...more languages
}
```

*   [View the full configuration file on GitHub](https://github.com/CodeStoryBuild/CodeStoryCli/blob/main/src/codestory/resources/language_config.json)

We are continuously working to support more languages. If you don't see your favorite language, feel free to submit a Pull Request to add it!

### What if the language is unknown?
You might be wondering what happens if a change does not match a defined language.

Depending on your configuration, CodeStory can perform some limited semantic analysis, either by grouping chunks that share matching file endings (e.g., all chunks in `.txt` files) or perhaps all changes that share the same file. 

And with that, you now have a solid understanding of the semantic engine driving CodeStory!