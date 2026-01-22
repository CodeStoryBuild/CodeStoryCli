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

## Getting Started

- **[Installation Guide](./getting-started/index.md)** - Get up and running in minutes.
- **[Philosophy](./philosophy/index.md)** - Why atomic commits and clean history matter.
- **[Usage Guide](./usage/index.md)** - Learn the <code>commit</code>, <code>fix</code>, and <code>clean</code> workflows.

## Deep Dives

- **[Architecture Overview](./design/how-it-works.md)** - How the pipeline coordinates analysis.
- **[Mechanical Chunking](./design/mechanical-chunking.md)** - Deterministic decomposition of diffs.
- **[Semantic Grouping](./design/semantic-grouping.md)** - Respecting code syntax with tree-sitter.
- **[Logical Grouping](./design/logical-grouping.md)** - Intent discovery and message generation.

## Reference

- **[Command Reference](./reference/root.md)** - CLI flags and detailed command usage.
- **[Configuration](./configuration/index.md)** - Settings and environment variables.
- **[Extensibility](./extensibility/index.md)** - Adding language support.
