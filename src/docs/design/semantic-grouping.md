# Semantic Grouping

Semantic grouping is the process of aggregating mechanical chunks into logical units based on the structure of the source code. This ensures that related changes stay together and that each commit results in syntactically valid code.

## Tree-sitter Integration
Codestory CLI uses [Tree-sitter](https://tree-sitter.github.io/tree-sitter/) to parse source files into Abstract Syntax Trees (ASTs). Unlike line-based diffs, ASTs provide a structured representation of the code, allowing the engine to understand the boundaries of functions, classes, and other logical blocks.

## Grouping Mechanisms

### 1. Scope-Based Grouping
The engine identifies the "scope" of each change. If a modification occurs within a function or class, the entire scope is treated as a single unit. This prevents a commit from containing only half of a function definition, which would break the build.

### 2. Symbol-Based Grouping (Links)
Codestory CLI tracks identifiers (symbols) across the codebase. If a change modifies a function definition, the engine can automatically group it with changes to the call sites of that function, even if they are in different files.

## Language Configuration
Each supported language has a configuration that defines how to identify scopes and symbols using Tree-sitter queries.

Example configuration for Python:
```json
{
    "python": {
        "root_node_name": "module",
        "shared_token_queries": {
            "identifier_class": {
                "general_queries": ["((identifier) @placeholder)"],
                "definition_queries": [
                  "(assignment left: (identifier) @placeholder)",
                  "(class_definition name: (identifier) @placeholder)",
                  "(function_definition name: (identifier) @placeholder)"
                ]
            }
        },
        "scope_queries": {
            "named_scope": [
                "((function_definition name: (identifier) @placeholder.name) @placeholder)",
                "((class_definition name: (identifier) @placeholder.name) @placeholder)"
            ]
        },
        "comment_queries": ["((comment) @placeholder)"],
        "share_tokens_between_files": "True"
    }
}
```

## Benefits
- **Syntactic Integrity**: Commits are guaranteed to be parsable.
- **Contextual Cohesion**: Related changes are kept together automatically.
- **Cross-File Intelligence**: Changes are linked across the project based on symbol usage.

**[Next: Logical Grouping](./logical-grouping.md)**