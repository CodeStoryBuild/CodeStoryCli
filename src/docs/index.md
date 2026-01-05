# Codestory CLI

Technical documentation for the Codestory CLI.

Codestory CLI is a tool for developers who value a clean, searchable, and reviewable Git history. It automates the creation of atomic commits from messy workflows

## Technical Pillars

- **Index-Only**: Operates on state snapshots; never disrupts your working directory.

- **Fully Sandboxed**: Analysis happens in isolated temporary storage to keep your `.git` folder clean.

- **Fully Atomic**: Your branch history is only updated if the entire pipeline succeeds.

- **Deterministic Semantic Analysis**: Before involving any AI, we use tree-sitter to understand the semantic structure of your code.

- **AI-Driven Semantic Clustering**: We use AI to cluster your changes based on higher level relationships that cannot be captured by syntax.


---

## Core Documentation

- **[Why Codestory CLI? (Philosophy)](./philosophy/index.md)**: Why atomic commits matter.

- **[Quick Start Guide](./getting-started/index.md)**: Installation and initial setup.

- **[Usage Guide](./usage/index.md)**: Workflow examples with `commit`, `fix`, and `clean`.

- **[Troubleshooting & Tips](./troubleshooting/index.md)**: How to refine behavior and resolve common issues.

## Technical Internals

Learn how we ensure safety and semantics:

- **[The Core Logic](./design/how-it-works.md)**: High-level overview of the pipeline.

- **[Mechanical Chunking](./design/mechanical-chunking.md)**: Deterministic decomposition of diffs.

- **[Semantic Grouping](./design/semantic-grouping.md)**: Using tree-sitter to respect syntax.

- **[Logical Grouping](./design/logical-grouping.md)**: AI-driven intent discovery.

- **[Commit Strategy](./design/commit-strategy.md)**: Safe history reconstruction.

## Reference

- **[CLI Reference](./reference/root.md)**: Command-line arguments and flags.

- **[Configuration](./configuration/index.md)**: Global, local, and environmental settings.

- **[Extensibility Guide](./extensibility/index.md)**: Adding support for new languages.

- **[Supported Lists](./reference/supported.md)**: AI providers and built-in languages.

---

Codestory CLI is licensed under GPLv2.
