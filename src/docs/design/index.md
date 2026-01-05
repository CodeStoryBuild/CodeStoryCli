# Architecture & Design

Explore the internal mechanics of Codestory CLI. Our architecture is designed to transform complex code changes into a clean, atomic history while maintaining safety and technical integrity at every step.

### Core Pipeline

- **[The Core Logic](./how-it-works.md)**: A high-level overview of how changes flow through our analysis engine.

- **[Mechanical Chunking](./mechanical-chunking.md)**: How we break down raw diffs into independent, atomic units.

- **[Semantic Grouping](./semantic-grouping.md)**: Using tree-sitter to understand the structural context of your code.

- **[Logical Grouping](./logical-grouping.md)**: The AI layer that identifies human intent and organizes changes into logical commits.

- **[Commit Strategy](./commit-strategy.md)**: How we safely reconstruct a new Git history from analyzed groups.
