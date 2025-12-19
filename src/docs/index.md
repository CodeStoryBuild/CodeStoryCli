# CodeStory CLI Documentation

### Main CLI Website [Here](https://cli.codestory.build)

## Getting Started

- **[Usage Guide](./usage/index.md)**: Practical examples for `commit`, `fix`, and `clean` commands.
- **[CLI Reference](./reference/root.md)**: Detailed command-line argument documentation.
- **[Supported Providers & Languages](./reference/supported.md)**: List of out-of-the-box integrations.

## Architecture & Design

Learn about the core pillars that power `codestory`:

- **[The Core Logic](./design/how-it-works.md)**: The high-level lifecycle of a change.
- **[Mechanical Chunking](./design/mechanical-chunking.md)**: How Git hunks are safely decomposed.
- **[Semantic Grouping](./design/semantic-grouping.md)**: Using Tree-sitter to respect language syntax.
- **[Logical Grouping](./design/logical-grouping.md)**: Using LLMs to understand intent and cross-file relationships.
- **[Commit Strategy](./design/commit-strategy.md)**: The incremental strategy for safe history rewriting.

## Extensibility

- **[Extensibility Guide](./extensibility/index.md)**: How to add support for new languages or customize behavior.

## License

`codestory` is licensed under GPLv2, following the same principles as Git.

