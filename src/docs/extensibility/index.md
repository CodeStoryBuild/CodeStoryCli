# Extensibility Guide

Codestory CLI is designed to be highly extensible, particularly in how it understands different programming languages. This guide explains how to add support for new languages or customize existing ones using tree-sitter queries.

## Language Configuration

Semantic grouping relies on tree-sitter to parse code and identify logical units (scopes) and identifiers. Each language's behavior is defined in a JSON configuration.

### Configuration Schema

A language configuration entry consists of several key components:

```json
{
  "language_name": {
    "root_node_name": "module",
    "shared_token_queries": {
      "identifier_class": {
        "general_queries": ["((identifier) @placeholder)"],
        "definition_queries": [
          "(assignment left: (identifier) @placeholder)",
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
    "share_tokens_between_files": true
  }
}
```

### Key Fields

#### `root_node_name`

The name of the top-level node in the tree-sitter grammar (e.g., `module` for Python, `program` for JavaScript).

#### `shared_token_queries`

Used to track identifiers across the codebase.

- **`general_queries`**: Matches all occurrences of identifiers.

- **`definition_queries`**: Matches only where an identifier is being defined or assigned. This is crucial for building a dependency graph of changes.

#### `scope_queries`

Defines what constitutes a "logical block" of code.

- **`named_scope`**: Matches nodes like functions, classes, or methods. The `@placeholder.name` capture should point to the identifier of the scope, while `@placeholder` captures the entire block.

#### `comment_queries`

Identifies comments and docstrings. These are linked to other code changes as context.

#### `share_tokens_between_files`

A boolean (`true` or `false`). If true, an identifier defined in one file can be linked to its usage in another file, allowing Codestory CLI to group cross-file changes logically.

## tree-sitter Queries

Codestory CLI uses the standard tree-sitter query syntax. You can test your queries using the tree-sitter CLI or online playgrounds.

### Captures

- `@placeholder`: The primary capture for identifiers or scopes.

- `@placeholder.name`: Specifically for the name of a scope (used in `named_scope`).

### Example: Python Function Definition

```query
((function_definition
    name: (identifier) @placeholder.name) @placeholder)
```

This query captures the entire `function_definition` node as the scope, and specifically identifies the `identifier` as the name of that scope.

## Adding a New Language

1. **Identify the Grammar**: Ensure the language is supported by `tree-sitter-language-pack`.

2. **Define Queries**: Write queries for identifiers, definitions, and scopes.

3. **Create JSON**: Wrap your queries in the configuration format shown above.

4. **Test**: Run `cst` with the `--custom-language-config` flag.

```bash
cst --custom-language-config ./my-lang.json commit
```

### Different ways to use custom configurations

#### Temporary Usage

```bash
# Use custom config for a single command
cst --custom-language-config /path/to/my_languages.json commit
```

#### Permanent Configuration

```bash
# Set custom config globally
cst config custom_language_config "/path/to/my_languages.json" --scope global

# Set custom config for current repository
cst config custom_language_config "/path/to/my_languages.json"
```

### Debugging Language Configurations

Enable verbose logging to see how your language configuration is being used:

```bash
cst -v [command]
```

### Best Practices

1. **Test Thoroughly**: Test your configuration on various code patterns.

2. **Use Specific Queries**: Make queries as specific as possible to avoid false matches.

3. **Handle Edge Cases**: Consider different declaration styles (arrow functions, decorators, etc.).

4. **Handle AST Structure**: Use tree-sitter tools to inspect the actual AST structure.

5. **Start Simple**: Begin with basic identifier and scope queries, then expand.

### Contributing Language Support

If you add support for a new language:

1. Test on multiple codebases.

2. Follow the existing JSON structure.

3. Consider submitting a pull request to the main Codestory CLI repository.

The language configuration files are located in `src/codestory/resources/language_config.json` in the Codestory CLI source code.
